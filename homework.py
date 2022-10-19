import os
import time
import logging
from typing import Dict
import requests
from requests import RequestException
from dotenv import load_dotenv

from telegram import Bot

from exceptions import APIResponseError, NoActiveHomeworksError, \
    APINotAvailableError, RequestExceptionError

logging.basicConfig(
    format='%(asctime)s - %(funcName)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    filename='main.log',
    filemode='a')
load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot: Bot, message: str):
    """
    отправляет сообщение в Telegram чат,
    определяемый переменной окружения TELEGRAM_CHAT_ID. Принимает
    на вход два параметра: экземпляр класса Bot и строку с текстом
    сообщения.
    """
    bot.send_message(TELEGRAM_CHAT_ID, message)


def get_api_answer(current_timestamp) -> Dict:
    """
    делает запрос к единственному
    эндпоинту API-сервиса. В качестве параметра функция получает
    временную метку. В случае успешного запроса должна вернуть
    ответ API, преобразовав его из формата JSON к типам данных Python.
    """
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response: requests.Response = requests.get(
            ENDPOINT, headers=HEADERS, params=params
        )
        if response.status_code != 200:
            raise APINotAvailableError(
                f"Ошибка при запросе к API: {response.status_code}"
            )
        return response.json()
    except RequestException as error:
        raise RequestExceptionError(logging.error(
            f'Ошибка при запросе к API: {error}'))


def check_response(response: Dict):
    """
    проверяет ответ API на корректность.
    В качестве параметра функция получает ответ API, приведенный
    к типам данных Python. Если ответ API соответствует ожиданиям,
    то функция должна вернуть список домашних работ (он может быть
    и пустым), доступный в ответе API по ключу 'homeworks'.
    """
    if response is None:
        raise APIResponseError(f"Ответ API некорректен: status-code != 200")
    if not isinstance(response, Dict):
        raise TypeError
    if 'error' in response:
        error_text = response['error']['error']
        raise APIResponseError(f"Ответ API некорректен: {error_text}")
    if 'homeworks' not in response:
        raise APIResponseError(f"Ответ API некорректен: нет homeworks.")
    if not isinstance(response['homeworks'], list):
        raise APIResponseError(f"Ответ API некорректен: homeworks не список.")
    if len(response['homeworks']) == 0:
        raise NoActiveHomeworksError(f"Нет активных домашних заданий.")
    return response['homeworks']


def parse_status(homework):
    """
    извлекает из информации о конкретной
    домашней работе статус этой работы. В качестве параметра
    функция получает только один элемент из списка домашних работ.
    В случае успеха, функция возвращает подготовленную для отправки
    в Telegram строку, содержащую один из вердиктов словаря
    HOMEWORK_STATUSES.
    """
    homework_name: str = homework['homework_name'].split('.')[0]
    homework_status: str = homework['status']
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """
    проверяет доступность переменных
    окружения, которые необходимы для работы программы. Если
    отсутствует хотя бы одна переменная окружения — функция должна
    вернуть False, иначе — True.
    """
    ENV_VARS = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
    }
    all_env_var_exists = True
    for env_var_name, env_var in ENV_VARS.items():
        if not env_var:
            all_env_var_exists = False
            logging.critical(f'Отсутствует переменная окружения:'
                             f'{env_var_name}')
    if all_env_var_exists:
        return True
    return False


def main():
    """Основная логика работы бота."""
    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    while True:
        logging.info("Запрашивается статус домашнего задания.")
        tokens_exist = check_tokens()
        if tokens_exist:
            n_sec_ago_moment = int(time.time() - RETRY_TIME)
            api_answer = get_api_answer(n_sec_ago_moment)
            try:
                response = check_response(api_answer)
                homework_status_message = parse_status(response[0])
                send_message(bot, homework_status_message)
                logging.info("Сообщение успешно отправлено в чат.")
            except (APIResponseError,
                    NoActiveHomeworksError,
                    APINotAvailableError,
                    RequestExceptionError):
                pass
        time.sleep(RETRY_TIME - (
                (time.time() - current_timestamp) % RETRY_TIME
        ))


if __name__ == '__main__':
    main()
