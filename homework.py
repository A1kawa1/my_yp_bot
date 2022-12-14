import time
import logging
import requests
import os
import sys
from http import HTTPStatus
import telegram
from telegram.ext import Updater, MessageHandler, CommandHandler, Filters
from dotenv import load_dotenv


load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG,
    filename='main.log',
    filemode='w'
)


def check_tokens():
    """проверка наличия всех необходимых переменных окружения."""
    if all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
        return True
    logging.critical('Нет обязательных переменных окружения')
    return False


def send_message(bot, message):
    """отправка сообщения message пользователю через bot."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message
        )
        logging.debug('Сообщение успешно отправлено')
    except telegram.error.TelegramError:
        logging.error('Сообщение не отправлено')


def get_api_answer(timestamp=0):
    """получения ответа от API Яндекс.Домашка."""
    PAYLOAD = {'from_date': timestamp}
    try:
        responce = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=PAYLOAD
        )
    except requests.RequestException as exception:
        raise exception('API временно не доступно')
    if responce.status_code == HTTPStatus.OK:
        return responce.json()
    raise requests.RequestException(
        f'{ENDPOINT} - {HEADERS} - {PAYLOAD} - {responce.status_code}'
    )


def check_response(response):
    """проверка ответа от API Яндекс.Домашка на валидность."""
    if not isinstance(response, dict):
        raise TypeError(
            'неверный формат ответа - в ответе не словарь'
        )
    if response.get('homeworks') is None:
        raise KeyError('отсутствует ключ homeworks')
    if not isinstance(response.get('homeworks'), list):
        raise TypeError(
            'неверный формат ответа - список дз это не список'
        )


def parse_status(homework):
    """получение статуса проекта."""
    if not isinstance(homework, dict):
        raise TypeError(
            'неверный формат ответа - полученное дз это не словарь'
        )

    if homework.get('homework_name') is None:
        raise KeyError('отсутствует ключ homework_name')
    homework_name = homework['homework_name']

    if homework.get('status') is None:
        raise KeyError('отсутствует ключ status')
    status = homework['status']

    if HOMEWORK_VERDICTS.get(status) is None:
        raise KeyError('некоректный status')
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def hello(update, context):
    button = telegram.ReplyKeyboardMarkup([['/by_date', '/last_project', '/stop']], resize_keyboard=True)
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        #text='от какой даты смотреть задание в формате Y-M-D H:M:S',
        text='выберите одну из команд',
        reply_markup=button
    )


def get_date(update, context):
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text='от какой даты смотреть задание в формате Y-M-D H:M:S'
    )


stopp = False
def main_loop(context, timestamp):
    if not check_tokens():
        sys.exit('отсутствуют необходимые переменный окружения')
    global stopp
    stopp = False
    previous_status = 0
    flag = False
    send_message(context.bot, 'вы начали отслеживание')
    while stopp == False:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            status = parse_status(response.get('homeworks')[0])
            if status != previous_status:
                previous_status = status
                send_message(context.bot, status)
        except Exception as error:
            if response.get('homeworks') == []:
                if flag == False:
                    send_message(context.bot, 'Ревью еще не началось')
                    flag = True
            else:
                message = f'Сбой в работе программы: {error}'
                logging.error(message)
                send_message(context.bot, message)
        finally:
            time.sleep(RETRY_PERIOD)
    logging.DEBUG('вы закончили отслеживание')


def by_date(update, context):
    times = update['message']['text']
    try:
        t=time.strptime(times,'%Y-%m-%d %H:%M:%S')
        timestamp = int(time.mktime(t))
    except:
        send_message(context.bot, 'неверная дата')
        return
    main_loop(context, timestamp)


def last_project(update, context):
    timestamp=0
    main_loop(context, timestamp)


def stop(update, context):
    global stopp
    stopp = True
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text='вы закончили отслеживание',
    )


def main():
    """Основная логика работы бота."""
    check_tokens()
    updater = Updater(token=TELEGRAM_TOKEN)
    updater.dispatcher.add_handler(CommandHandler('start', hello))
    updater.dispatcher.add_handler(CommandHandler('by_date', get_date))
    updater.dispatcher.add_handler(CommandHandler('last_project', last_project, run_async=True))
    updater.dispatcher.add_handler(CommandHandler('stop', stop))
    updater.dispatcher.add_handler(MessageHandler(Filters.text, by_date, run_async=True))
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
