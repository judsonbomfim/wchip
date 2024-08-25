from pathlib import Path
import os
import boto3
from django.contrib.messages import constants as messages
from celery.schedules import crontab
from datetime import timedelta
from dotenv import load_dotenv
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = str(os.getenv('SECRET_KEY'))

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = [
    h.strip() for h in os.getenv('ALLOWED_HOSTS', '').split(',')
    if h.strip()
]

CSRF_TRUSTED_ORIGINS = [
    a.strip() for a in os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',')
    if a.strip()
]

SESSION_ENGINE = 'django.contrib.sessions.backends.db'

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'storages',
    'rolepermissions',
    'django_celery_beat',
    'apps.orders.apps.OrdersConfig',
    'apps.sims.apps.SimsConfig',
    'apps.dashboard.apps.DashboardConfig',
    'apps.users.apps.UsersConfig',
    'apps.send_email.apps.SendEmailConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'


# Database

# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.sqlite3',
#         'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
#     }
# }


DATABASES = {
    'default': {
        'ENGINE': os.getenv('DB_ENGINE'),
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST'),
        'PORT': os.getenv('DB_PORT'),
    }
}

# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
DATE_INPUT_FORMATS = ('%d/%m/%Y',)
USE_I18N = True
USE_L10N = True
USE_TZ = False

DATE_FORMAT = '%d/%m/%Y'

DATA_UPLOAD_MAX_NUMBER_FILES = 1000

# Expirar sessão em 10h
SESSION_COOKIE_AGE = 36000


URL_PAINEL = str(os.getenv('URL_PAINEL'))
URL_CDN = 'https://'+str(os.getenv('URL_CDN'))


AWS_ACCESS_KEY_ID = str(os.getenv('AWS_ACCESS_KEY_ID'))
AWS_SECRET_ACCESS_KEY = str(os.getenv('AWS_SECRET_ACCESS_KEY'))
AWS_STORAGE_BUCKET_NAME = str(os.getenv('AWS_STORAGE_BUCKET_NAME'))
AWS_S3_CUSTOM_DOMAIN = str(os.getenv('AWS_S3_CUSTOM_DOMAIN'))
AWS_DEFAULT_ACL = None
AWS_S3_OBJECT_PARAMETERS = {
    'CacheControl': 'max-age=86400',
}

STATIC_LOCATION = 'static'

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'core/static'),
]

STATIC_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/{STATIC_LOCATION}/'
STATICFILES_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'

MEDIA_LOCATION = 'media'
MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/{MEDIA_LOCATION}/'
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.MediaStorage'


# Default primary key field type
# https://docs.djangoproject.com/en/4.1/ref/settings/#default-auto-field


MESSAGE_TAGS = {
    messages.DEBUG: 'primary',
    messages.ERROR: 'danger',
    messages.SUCCESS: 'success',
    messages.INFO: 'info',
    messages.WARNING: 'warning',
}

ROLEPERMISSIONS_MODULE = 'core.roles'
KEYCLOAK_PERMISSIONS_METHOD = 'role'    

# E-mail
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = str(os.getenv('EMAIL_HOST'))
EMAIL_PORT = 587
EMAIL_HOST_USER = str(os.getenv('EMAIL_HOST_USER'))
EMAIL_HOST_PASSWORD = str(os.getenv('EMAIL_HOST_PASSWORD'))
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False
DEFAULT_FROM_EMAIL = str(os.getenv('DEFAULT_FROM_EMAIL'))


# CELERY

CELERY_BROKER_URL = str(os.getenv('CELERY_BROKER_URL'))
CELERY_RESULT_BACKEND = str(os.getenv('CELERY_RESULT_BACKEND'))

CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
CELERY_BEAT_SYNC_EVERY = None

CELERY_TIMEZONE = 'Europe/London'

CELERY_BEAT_SCHEDULE = {
    'task__5_min_orders_auto': {
        'task': 'apps.orders.tasks.orders_auto',
        'schedule': crontab(minute='*/1'),
    },
    # 'task__5_min_activate_TC': {
    #     'task': 'apps.sims.tasks.simActivateTC',
    #     # 'schedule': crontab(minute='2-59/5'),
    #     'schedule': crontab(minute='*/1'),
    # },
    # 'task__deactivate_TC': {
    #     'task': 'apps.sims.tasks.simDeactivateTC',
    #     'schedule': crontab( hour=23, minute=50),
    # },
}


# API TELCON

APITC_USERNAME = str(os.getenv('APITC_USERNAME'))
APITC_PASSWORD = str(os.getenv('APITC_PASSWORD'))
APITC_HTTPCONN = str(os.getenv('APITC_HTTPCONN'))
