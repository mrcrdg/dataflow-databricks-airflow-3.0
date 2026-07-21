# # Log:

# #rows processed
# #rows failed
# #execution time

# log.info({
#     "stage": "bronze_posts",
#     "rows_in": 10000,
#     "rows_valid": 9800,
#     "rows_invalid": 200
# })


import logging
import sys


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)

        formatter = logging.Formatter(
            fmt='%(asctime)s | %(levelname)s | %(name)s | %(message)s'
        )

        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    return logger