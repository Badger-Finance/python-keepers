import logging
import traceback
from types import TracebackType
from typing import Any
from typing import Type

from pythonjsonlogger import jsonlogger

logger = logging.getLogger()


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record: Any, record: logging.LogRecord, message_dict: dict):
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)
        if log_record.get('level'):
            log_record['logger_severity'] = log_record['level'].upper()
        else:
            log_record['logger_severity'] = getattr(record, 'levelname', "NOTSET")


log_handler = logging.StreamHandler()
formatter = CustomJsonFormatter()
log_handler.setFormatter(formatter)
logger.addHandler(log_handler)
logger.setLevel(logging.INFO)


def exception_logging(
        exctype: Type[BaseException], value: BaseException, tb: TracebackType) -> None:
    logger.error(f"{str(exctype)} Exception", extra={
        'exctype': str(exctype),
        'error': ''.join(traceback.format_exception(exctype, value, tb))
    })
