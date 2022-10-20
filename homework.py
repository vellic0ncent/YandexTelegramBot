import os
import time
import logging
from http import HTTPStatus
from typing import Dict, NoReturn, Union, List
import requests
from requests import RequestException
from dotenv import load_dotenv

from telegram import Bot

from exceptions import APIResponseError, NoActiveHomeworksError, \
    APINotAvailableError, RequestExceptionError, SendMessageError, \
    WarningError, CriticalError

logging.basicConfig(
    format="%(asctime)s - %(funcName)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    filename="main.log",
    filemode="a")
load_dotenv()


PRACTICUM_TOKEN = os.getenv("PRACTICUM_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

HEADERS = {"Authorization": f"OAuth {PRACTICUM_TOKEN}"}

RETRY_TIME = 600
ENDPOINT = "https://practicum.yandex.ru/api/user_api/homework_statuses/"


HOMEWORK_STATUSES = {
    "approved": "Работа проверена: ревьюеру всё понравилось. Ура!",
    "reviewing": "Работа взята на проверку ревьюером.",
    "rejected": "Работа проверена: у ревьюера есть замечания."
}


def send_message(bot: Bot, message: str) -> NoReturn:
    """
    Отправляет сообщение в Telegram чат.

    Определяемый переменной окружения TELEGRAM_CHAT_ID. Принимает на вход два
    параметра: экземпляр класса Bot и строку с текстом сообщения.
    """
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception as e:
        raise SendMessageError(str(e))


def get_api_answer(current_timestamp: int) -> Dict[str, Union[List, int]]:
    """
    Делает запрос к единственному эндпоинту API-сервиса.

    В качестве параметра функция получает временную метку. В случае успешного
    запроса должна вернуть ответ API, преобразовав его из формата JSON к типам
    данных Python.
    """
    timestamp: int = current_timestamp or int(time.time())
    request_params = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': {"from_date": timestamp}
    }
    try:
        response: requests.Response = requests.get(
            **request_params
        )
        if response.status_code != HTTPStatus.OK:
            raise APINotAvailableError(
                f"Ошибка при запросе к API:"
                f"код: {response.status_code}, "
                f"текст ошибки: {response.text}, "
                f"endpoint: {ENDPOINT}, "
            )
        return response.json()
    except RequestException as error:
        raise RequestExceptionError(
            f"Ошибка при запросе к API: {error.response}, "
            f"endpoint: {ENDPOINT}, "
            f"{error.request}.")


def check_response(response: Dict) -> List[Dict[str, Union[str, int]]]:
    """
    Проверяет ответ API на корректность.

    В качестве параметра функция получает ответ API, приведенный к типам
    данных Python. Если ответ API соответствует ожиданиям, то функция должна
    вернуть список домашних работ (он может быть и пустым), доступный в ответе
    API по ключу 'homeworks'.
    """
    if not isinstance(response, Dict):
        raise TypeError("Ответ API некорректен: ожидался Dict, "
                        f"пришел {type(response)}.")
    if "error" in response:
        error_text = response["error"]["error"]
        raise APIResponseError(f"Ответ API некорректен: {error_text}")
    if "homeworks" not in response:
        raise KeyError("Ответ API некорректен: нет homeworks. Ответ имеет "
                       f"ключи: {response.keys()}.")
    if not isinstance(response["homeworks"], list):
        raise KeyError("Ответ API некорректен: homeworks не список, а "
                       f"{type(response['homeworks'])}, имеет вид: "
                       f"{response['homeworks']}")
    if len(response["homeworks"]) == 0:
        raise NoActiveHomeworksError("Нет активных домашних заданий.")
    return response["homeworks"]


def parse_status(homework) -> str:
    """
    Извлекает из информации о конкретной домашней работе статус этой работы.

    В качестве параметра функция получает только один элемент из списка
    домашних работ. В случае успеха, функция возвращает подготовленную для
    отправки в Telegram строку, содержащую один из вердиктов словаря
    HOMEWORK_STATUSES.
    """
    homework_name: str = homework.get("homework_name", None)
    homework_status: str = homework.get("status", None)
    if not homework_name:
        raise KeyError("Отсутствует название домашнего задания. Есть ключи: "
                       f"{homework.keys()}.")
    if not homework_status:
        raise KeyError("Отсутствует статус домашнего задания. Есть ключи: "
                       f"{homework.keys()}.")
    verdict: str = HOMEWORK_STATUSES.get(homework_status, None)
    if not verdict:
        raise KeyError("Отсутствует статус домашнего задания в "
                       f"HOMEWORK_STATUSES. Новый статус: {homework_status}.")
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens() -> bool:
    """
    Проверяет доступность переменных окружения, которые необходимы для работы.

    Если отсутствует хотя бы одна переменная окружения — функция должна
    вернуть False, иначе — True.
    """
    ENV_VARS = {
        "PRACTICUM_TOKEN": PRACTICUM_TOKEN,
        "TELEGRAM_TOKEN": TELEGRAM_TOKEN,
        "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID,
    }
    all_env_var_exists: bool = True
    for env_var_name, env_var in ENV_VARS.items():
        if not env_var:
            all_env_var_exists = False
            logging.critical("Отсутствует переменная окружения:"
                             f"{env_var_name}.")
    return all_env_var_exists


def main() -> NoReturn:
    """Основная логика работы бота."""
    bot: Bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp: int = int(time.time())
    logging.info("Получение статуса домашнего задания.")
    logging.info("Проверка наличия переменных окружения (токенов).")
    tokens_exist: bool = check_tokens()
    if tokens_exist:
        while True:
            moment: int = int(time.time() - RETRY_TIME // 2)
            try:
                logging.info("Запрос к эндпойнту API-сервиса.")
                api_answer: Dict[str, Union[List, int]] = get_api_answer(
                    moment
                )
                logging.info("Проверка корректности ответа API.")
                response: List[Dict[str, Union[str, int]]] = check_response(
                    api_answer
                )
                logging.info(
                    "Получаем из ответа API информацию о последней работе."
                )
                homework_status_message: str = parse_status(response[0])
                logging.info("Отправка сообщения в телеграм.")
                send_message(bot, homework_status_message)
                logging.info("Сообщение успешно отправлено в чат.")
            except WarningError as error:
                logging.info(str(error))
            except CriticalError as error:
                logging.error(str(error))
                send_message(bot=bot, message=str(error))
            finally:
                time.sleep(
                    RETRY_TIME - (
                            (time.time() - current_timestamp) % RETRY_TIME
                    )
                )


if __name__ == '__main__':
    main()
