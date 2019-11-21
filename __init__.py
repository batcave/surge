from fabulous import red


## Example settings
# USER = "intranet"
# GROUP = "intranet"
# HOST = 'ticketing.protectamerica.com'
#
# PROD_SETTINGS = deploy.BASE_SETTINGS(
#     HOST=HOST,
#     DEPLOY_PATH='/deploy/intranet',
#     USER=USER,
#     GROUP=GROUP,
#     BOUNCE_SERVICES=[
#         'intranet',
#         'intranet_celery',
#         'intranet_celerybeat',
#         'intranet_mail',
#         'intranet_snet',
#         'intranet_custidx'
#     ],
#     EXTRA_COMMANDS=[
#         'sudo cp crons/-etc-cron.d-restart_intranet_mail /etc/cron.d/restart_intranet_mail',
#         'sudo chown root:root /etc/cron.d/restart_intranet_mail',
#         # 'touch collected-assets/less/style.less',
#     ],
#     CRON_FILE='/deploy/intranet/confs/intranet/crontab.txt'
# )
#
# env.host_string = PROD_SETTINGS.HOST
# env.deploy_settings = PROD_SETTINGS
##


DEFAULT_SETTINGS = dict(
    REQUIRE_CLEAN=True,
    BRANCH_NAME='master',
    DJANGO_PROJECT=True,
    SKIP_SYNCDB=False,
    SKIP_MIGRATE=False,
    RESTART_NGINX=False,
    BOUNCE_SERVICES_ONLY_IF_RUNNING=False,
    OS_SERVICE_MANAGER='upstart',
    REQUIRE_REMOTE_CLEAN=True,
)

REQUIRED_SETTINGS = [
    'HOST',
    'USER',
    'GROUP',
    'DEPLOY_PATH',
]

class BASE_SETTINGS(object):
    def __init__(self, *args, **kwargs):
        self.kwargs = boold_up(kwargs)  # Keep track of original supplied settings
        self.settings = {}  # Keep a dictionary of all the settings
        self.settings.update(DEFAULT_SETTINGS)
        env['surge_stack'] = None  # Used by @surge_stack logic

        self.update(kwargs)

    def update(self, settings):
        new_settings = boold_up(settings)
        if 'CRONTAB_OWNER' not in self.kwargs:
            self.settings['CRONTAB_OWNER'] = new_settings.get('USER', self.kwargs['USER'])
        
        self.CHOWN_TARGET = '{0}:{1}'.format(
            new_settings.get('USER', self.kwargs['USER']),
            new_settings.get('GROUP', self.kwargs['GROUP'])
        )

        self.settings['GIT_TREE'] = new_settings.get('DEPLOY_PATH', self.kwargs['DEPLOY_PATH'])

        # Overide any of these automatically set settings from new_settings
        self.settings.update(new_settings)
        
        sreq = frozenset(REQUIRED_SETTINGS)
        sset = frozenset(self.settings.keys())
        missing = sreq.difference(sset)

        empty = [k for k in REQUIRED_SETTINGS if not isinstance(self.settings[k], str) and self.settings[k] != '']

        if missing or empty:
            print(red("Required settings are missing; {0}".format(', '.join(missing))))
            raise ValueError


        # Make them attributes
        self.__dict__.update(self.settings)










