from pathlib import Path
import environ
import os
import boto3
from django.contrib.messages import constants as messages
from celery.schedules import crontab
from datetime import timedelta
from dotenv import load_dotenv
load_dotenv()


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Inicialize o `environ`
env = environ.Env(
    DEBUG=(bool, False)
)
# Leia o arquivo `.env`
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = str(env('SECRET_KEY'))

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# Certifique-se de que cast não seja sobrescrito
ALLOWED_HOSTS = [h.strip() for h in env('ALLOWED_HOSTS', default='').split(',')]


CSRF_TRUSTED_ORIGINS = [a.strip() for a in env('CSRF_TRUSTED_ORIGINS', default='').split(',')]


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
        'ENGINE': env('DB_ENGINE'),
        'NAME': env('DB_NAME'),
        'USER': env('DB_USER'),
        'PASSWORD': env('DB_PASSWORD'),
        'HOST': env('DB_HOST'),
        'PORT': env('DB_PORT'),
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


URL_PAINEL = str(env('URL_PAINEL'))
URL_CDN = 'https://'+str(env('URL_CDN'))


AWS_ACCESS_KEY_ID = str(env('AWS_ACCESS_KEY_ID'))
AWS_SECRET_ACCESS_KEY = str(env('AWS_SECRET_ACCESS_KEY'))
AWS_STORAGE_BUCKET_NAME = str(env('AWS_STORAGE_BUCKET_NAME'))
AWS_S3_CUSTOM_DOMAIN = str(env('AWS_S3_CUSTOM_DOMAIN'))
AWS_DEFAULT_ACL = None
# AWS_S3_OBJECT_PARAMETERS = {
#     'CacheControl': 'max-age=86400',
# }

STATIC_LOCATION = 'static'

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'core/static'),
]

STATIC_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/{STATIC_LOCATION}/'
STATICFILES_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
STATIC_ROOT = os.path.join(BASE_DIR, 'static')


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
EMAIL_HOST = str(env('EMAIL_HOST'))
EMAIL_PORT = 587
EMAIL_HOST_USER = str(env('EMAIL_HOST_USER'))
EMAIL_HOST_PASSWORD = str(env('EMAIL_HOST_PASSWORD'))
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False
DEFAULT_FROM_EMAIL = str(env('DEFAULT_FROM_EMAIL'))


# CELERY

CELERY_BROKER_URL = str(env('CELERY_BROKER_URL'))
CELERY_RESULT_BACKEND = str(env('CELERY_RESULT_BACKEND'))

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

APITC_USERNAME = str(env('APITC_USERNAME'))
APITC_PASSWORD = str(env('APITC_PASSWORD'))
APITC_HTTPCONN = str(env('APITC_HTTPCONN'))

# SSL
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
