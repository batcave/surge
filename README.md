# surge
fabric deploy stuff

## BASE_SETTINGS Class
This will be what you set your various depoloy targets from.

It will self update from the DEFAULT_SETTINGS dictionary on instantation.

The bare minimium kwargs required on instantiation are:

* USER
* GROUP
* HOST
* DEPLOY_PATH

It will also set:

* CRONTAB_OWNER
* CHOWN_TARGET
* GIT_TREE

Based on the provided USER, GROUP, and DEPLOY\_PATH kwargs when instantiating BASE\_SETTINGS.

## DEFAULT_SETTINGS dictionary
``` Python
DEFAULT_SETTINGS = dict(
    REQUIRE_CLEAN=True,
    SKIP_SYNCDB=False,
    SKIP_MIGRATE=False,
    BRANCH_NAME='master',
    DJANGO_PROJECT=True,
    RESTART_NGINX=False,
    BOUNCE_SERVICES_ONLY_IF_RUNNING=False,
)
```

## Example for a projects fabfile.py
``` Python
import surge as deploy

PROD_SETTINGS = deploy.BASE_SETTINGS(
    HOST='ticketing.protectamerica.com,
    DEPLOY_PATH='/deploy/intranet',
    USER='intranet',
    GROUP='intranet',
    BOUNCE_SERVICES=[
        'intranet',
        'intranet_celery',
        'intranet_celerybeat',
        'intranet_mail',
        'intranet_snet',
        'intranet_custidx'
    ],
    EXTRA_COMMANDS=[
        'sudo cp crons/-etc-cron.d-restart_intranet_mail /etc/cron.d/restart_intranet_mail',
        'sudo chown root:root /etc/cron.d/restart_intranet_mail',
        # 'touch collected-assets/less/style.less',
    ]
)

deploy.env.host_string = PROD_SETTINGS.HOST
deploy.env.deploy_settings = PROD_SETTINGS

```
You can add additional project specific deployment commands by adding @task decorators to any function.


## Alternate deployment targets
To have additional deployment targets create a new fabfile importing surge and named accordingly. ```fab_training.py``` for example.

Then just call fab using this file:
``` fab deploy -f fab_training.py```

``` Python
import surge as deploy

TRAINING_SETTINGS = deploy.BASE_SETTINGS(
    HOST='ticketing.protectamerica.com,
    DEPLOY_PATH='/deploy/intranettraining',
    USER='intranettraining',
    GROUP='intranettraining',
    BOUNCE_SERVICES=[
        'intranettraining',
        'intranettraining_celery',
        'intranettraining_celerybeat',
        'intranettraining_mail',
        'intranettraining_snet',
        'intranettraining_custidx'
    ]
)

deploy.env.host_string = TRAINING_SETTINGS.HOST
deploy.env.deploy_settings = TRAINING_SETTINGS

```

## Example usage
```
fab list
fab deploy
fab deploy -f fab_training.py  # will run against this alternate deployment target
fab deploy:require_clean=False
fab deploy:require_clean=False,skip_syncdb=True,skip_migrate=True

fab deploy.show_settings
fab deploy.bounce_services:restart_nginx=True
fab deploy.services_status
fab deploy.restart_nginx -f fab_training.py
fab deploy.is_remote_clean -f fab_training.py
fab deploy.pull:branch=new-feature
fab deploy.fix_ownerships
```

## Deploy commands
```
Available commands:
    deploy
        Any setting can be overridden by supplying :SETTING_A=X,SETTING_B=Y,...
    deploy.bounce_services
        :restart_nginx=True|False (default=False)
        :bounce_services_only_if_running=True|False (default=False)
    deploy.collectstatic
    deploy.fix_logfile_permissions
    deploy.fix_ownerships
    deploy.full_deploy (default command as deploy)
        Any setting can be overridden by supplying :SETTING_A=X,SETTING_B=Y,...
    deploy.full_deploy_with_migrate
    deploy.install_requirements
    deploy.is_local_clean
    deploy.is_remote_clean
    deploy.pull
        :branch=branch_name
    deploy.restart_nginx
    deploy.run_extras
    deploy.run_migrations
    deploy.services_status
    deploy.show_settings
        Will display the deployment targets configured settings
    deploy.sync_db
    deploy.update_crontab
    deploy.update_submodules
```

# Settings
Settings utilized for a standard full_deploy (as kwargs)

Instaniate a BASE_SETTINGS Class with these kwargs provided as needed


## Required

### HOST
The hostname where the fabric commands will be executed

### DEPLOY_PATH
The project location on the HOST

### USER
The name of the owner for the files on this project and it's deployment

### GROUP
The name of the group for the files on this project and it's deployment


## Defaults (Provided from DEFAULT\_SETTINGS dictionary and automatically set in BASE\_SETTINGS Class)
### REQUIRE_CLEAN (True)
Require that the local repoository be clean before proceeding with a deploy

### SKIP_SYNCDB (False)
Skip the ./manage syncdb command in a DJANGO_PROJECT deploy

### SKIP_MIGRATE (False)
Skip the ./manage migrate command in a DJANGO_PROJECT deploy

### BRANCH_NAME (master)
The git branch to pull from during a deploy

### DJANGO_PROJECT (True)
Whether this project is based on Django. Will run Django specific commands during a deploy

If DJANGO_PROJECT is False the sync_db(), collectstatic(), and run_migrations() commands will not be run regardless of the SKIP_SYNCDB and SKIP_MIGRATE settings

### RESTART_NGINX (False)
Restart the nginx process along with bouncing services

### BOUNCE_SERVICES_ONLY_IF_RUNNING (False)
Only (re)start the services if they are running


## Optional
### EXTRA_COMMANDS
This is a list of strings representing exact commands that will be run on the host
at the end of the standard deploy process

### CRON_FILE
The path to the file that will be replace the cron for the CRONTAB_OWNER

### CRONTAB_OWNER
User to load CRON_FILE under
Will default to USER if not set

### CHOWN_TARGET
user:group to set ownership of files to in the DEPLOY_PATH
Will default to USER:GROUP if not supplied

### BOUNCE_SERVICES
The list of service names that will be restarted at the end of the deployment

