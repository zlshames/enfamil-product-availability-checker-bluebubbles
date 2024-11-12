import json
import bs4
import os
import requests
import schedule
import time
import logging

# load from .env
from dotenv import load_dotenv
load_dotenv()

BLUEBUBBLES_SERVER = os.getenv('BLUEBUBBLES_SERVER')
BLUEBUBBLES_PASSWORD = os.getenv('BLUEBUBBLES_PASSWORD')

IMESSAGE_PREAMBLE = os.getenv('IMESSAGE_PREAMBLE')
IMESSAGE_RECIPIENT = os.getenv('IMESSAGE_RECIPIENT')

ENFAMIL_PRODUCT_NAME = os.getenv('ENFAMIL_PRODUCT_NAME')
ENFAMIL_PRODUCT_ID = os.getenv('ENFAMIL_PRODUCT_ID')

INTERVAL = int(os.getenv('INTERVAL')) if os.getenv('INTERVAL') else 30

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logging.getLogger('requests').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Allow requests to accept cookies
session = requests.Session()

# Allow us to wait until the product goes unavailable before sending an alert
waiting_until_unavailable = False


def send_imeessage_bluebubbles(message, method='private-api', subject=None):
    payload = {
        "chatGuid": f"iMessage;-;{IMESSAGE_RECIPIENT}",
        "message": message,
        "method": method,
        "subject": subject
    }
    response = requests.post(
        f'{BLUEBUBBLES_SERVER}/api/v1/message/text',
        params={'password': BLUEBUBBLES_PASSWORD},
        data=json.dumps(payload),
        headers={
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    )

    return response.json()


def get_product_url():
    return f'https://www.enfamil.com/products/{ENFAMIL_PRODUCT_ID}'


def is_available():
    global waiting_until_unavailable

    res = session.get(
        get_product_url(),
        # Impersonate a browser
        headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Accept': 'text/html,application/xhtml+xml,application/xml',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-User': '?1',
            'Sec-Fetch-Dest': 'document',
            'Cache-Control': 'max-age=0',
            'Pragma': 'no-cache',
            'Host': 'www.enfamil.com'
        }
    )
    res.raise_for_status()

    soup = bs4.BeautifulSoup(res.text, 'html.parser')
    availability_string = str(soup.find('div', class_='product-options__price-stock').text).strip()
    return "In Stock" in availability_string
    

def check():
    global waiting_until_unavailable

    available = is_available()
    if available and waiting_until_unavailable:
        logger.info(f'Product is already available! Waiting {INTERVAL} seconds before checking again...')
    elif available:
        logger.info('Product is now available! Sending iMessage alert...')
        send_imeessage_bluebubbles(
            f'{IMESSAGE_PREAMBLE if IMESSAGE_PREAMBLE else ''}{ENFAMIL_PRODUCT_NAME} is now available! {get_product_url()}',
            subject='Enfamil Product Alert!'
        )

        logger.info('Waiting for it to go out of stock...')
        waiting_until_unavailable = True
    else:
        logger.info(f'Product is still unavailable. Will check again in {INTERVAL} seconds...')


if __name__ == '__main__':
    logger.info(f'Checking Enfamil product availability for product ID: {ENFAMIL_PRODUCT_ID}')
    available = is_available()
    if available:
        logger.info(f'Product is already available! Waiting {INTERVAL} seconds before checking again...')
        waiting_until_unavailable = True
    else:
        logger.info(f'Product is currently unavailable. Will check again in {INTERVAL} seconds...')

    # Scheduling the task to run every 10 seconds
    schedule.every(30).seconds.do(check)

    while True:
        schedule.run_pending()
        time.sleep(10)