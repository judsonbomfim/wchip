from pathlib import Path
import environ
import os
import boto3
from urllib.parse import urlparse
from django.contrib.messages import constants as messages
from celery.schedules import crontab
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

# Leia a variável de ambiente DEBUG
debug_mode = env('DEBUG')

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = str(env('SECRET_KEY'))

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# Certifique-se de que cast não seja sobrescrito
ALLOWED_HOSTS = [h.strip() for h in env('ALLOWED_HOSTS', default='').split(',')]

def _normalize_origin(value):
    value = (value or '').strip()
    if not value:
        return ''
    if not value.startswith(('http://', 'https://')):
        return ''
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        return ''
    return f'{parsed.scheme}://{parsed.netloc}'


csrf_origins_env = [
    _normalize_origin(a)
    for a in env('CSRF_TRUSTED_ORIGINS', default='').split(',')
]
csrf_origins = {origin for origin in csrf_origins_env if origin}

url_painel = _normalize_origin(env('URL_PAINEL', default=''))
if url_painel:
    csrf_origins.add(url_painel)

CSRF_TRUSTED_ORIGINS = sorted(csrf_origins)


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
        'OPTIONS': {
            'sslmode': env('DB_SSLMODE', default='prefer')
        },
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
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'


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

CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = False
DJANGO_CELERY_BEAT_TZ_AWARE = False

CELERY_BEAT_SCHEDULE = {
    'task__2_min_orders_auto': {
        'task': 'apps.orders.tasks.orders_auto',
        'schedule': crontab(minute='2-58/2'),  # grupo A: min 02, 04, 06...
    },
    'task__2_min_activate_TC': {
        'task': 'apps.sims.tasks.simActivateTC',
        'schedule': crontab(minute='2-58/2'),  # grupo A
    },
    'task__2_min_activate_EO': {  # T-mobile/ Verizon
        'task': 'apps.sims.tasks.simActivateEO',
        'schedule': crontab(minute='3-59/2'),  # grupo B: min 03, 05, 07...
    },
    'task__deactivate_TC': {
        'task': 'apps.sims.tasks.simDeactivateTC',
        'schedule': crontab(hour=0, minute=0),
    },
    'task__deactivate_all': {
        'task': 'apps.sims.tasks.simDeactivateAll',
        'schedule': crontab(hour=0, minute=0),
    },
    'task__2_min_activate_CM': {
        'task': 'apps.sims.tasks.simActivateCM',
        'schedule': crontab(minute='2-58/2'),  # grupo A
    },
    'task__2_min_activate_AR': {
        'task': 'apps.sims.tasks.simActivateAR',
        'schedule': crontab(minute='3-59/2'),  # grupo B
    },
}


# API TELCON
APITC_USERNAME = str(os.getenv('APITC_USERNAME'))
APITC_PASSWORD = str(os.getenv('APITC_PASSWORD'))
APITC_HTTPCONN = str(os.getenv('APITC_HTTPCONN'))

# API CHINA MOBILE
APICM_KEY = str(os.getenv('APICM_KEY'))
APICM_SECRET = str(os.getenv('APICM_SECRET'))
APICM_URL = str(os.getenv('APICM_URL'))

# API TM / VERIZON
APIEO_TOKEN = str(os.getenv('APIEO_TOKEN'))
APIEO_URL = str(os.getenv('APIEO_URL'))

# API AIRALO
APIAIRALO_KEY = str(os.getenv('APIAIRALO_KEY'))
APIAIRALO_SECRET = str(os.getenv('APIAIRALO_SECRET'))
APIAIRALO_URL = str(os.getenv('APIAIRALO_URL'))


# LOGGING CONFIGURATION
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {message}',
            'style': '{',
        },
        'detailed': {
            'format': '[{asctime}] {levelname} [{name}:{lineno}] - {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
    },
    'filters': {
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'app.log'),
            'maxBytes': 1024 * 1024 * 15,  # 15MB
            'backupCount': 10,
            'formatter': 'detailed',
        },
        'file_error': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'error.log'),
            'maxBytes': 1024 * 1024 * 15,  # 15MB
            'backupCount': 10,
            'formatter': 'detailed',
        },
        'celery_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'celery.log'),
            'maxBytes': 1024 * 1024 * 15,  # 15MB
            'backupCount': 10,
            'formatter': 'detailed',
        },
        'sims_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'sims.log'),
            'maxBytes': 1024 * 1024 * 15,  # 15MB
            'backupCount': 10,
            'formatter': 'detailed',
        },
        'orders_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'orders.log'),
            'maxBytes': 1024 * 1024 * 15,  # 15MB
            'backupCount': 10,
            'formatter': 'detailed',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
        'django.request': {
            'handlers': ['file_error'],
            'level': 'ERROR',
            'propagate': False,
        },
        'celery': {
            'handlers': ['console', 'celery_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps.sims': {
            'handlers': ['console', 'sims_file', 'file_error'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps.orders': {
            'handlers': ['console', 'orders_file', 'file_error'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps.send_email': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps.users': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
    'root': {
        'handlers': ['console', 'file', 'file_error'],
        'level': 'INFO',
    },
}