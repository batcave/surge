from getpass import getpass

from fabric.util import get_local_user

from .util import random_string
from .watchers import CallbackResponder


class PromptingRunner:
    def __init__(self, runner):
        self.runner = runner
    
    def __getattr__(self, key):
        ###FIXME: This doesn't work because of a __setstate__ call in invoke.config.merge_dicts via copy
        return getattr(self.runner, key)
    
    def sudo(self, command, **kwargs):
        ###NOTE: code largely stolen from invoke:invoke.context:Context._sudo
        
        prompt = kwargs.pop('prompt', self.config.sudo.prompt)
        password = kwargs.pop("password", self.config.sudo.password)
        user = kwargs.pop("user", self.config.sudo.user)
        memoize_password = kwargs.pop('memoize_password', self.config.sudo.memoize_password)
        
        #unique prompt
        if not prompt:
            prompt = '[{}]'.format(random_string())
        
        user_flags = ""
        if user is not None:
            user_flags = f"-Hu {user} "
        
        #prompt for password
        if not password:
            user = user or get_local_user()
            user_prompt = f'[sudo] password for {user} on {self.config.host}: '
            password = lambda: self.prompt_for_password(user_prompt, memoize_password)
        
        command = self._prefix_commands(command)
        cmd_str = f"sudo -Sp '{prompt}' {user_flags}{command}"
        watcher = CallbackResponder(
            pattern=re.escape(prompt),
            response=password,
            sentinel="Sorry, try again.\n",
        )
        # Ensure we merge any user-specified watchers with our own.
        # NOTE: If there are config-driven watchers, we pull those up to the
        # kwarg level; that lets us merge cleanly without needing complex
        # config-driven "override vs merge" semantics.
        # TODO: if/when those semantics are implemented, use them instead.
        # NOTE: config value for watchers defaults to an empty list; and we
        # want to clone it to avoid actually mutating the config.
        watchers = kwargs.pop("watchers", list(self.config.run.watchers))
        watchers.append(watcher)
        try:
            return self.runner.run(cmd_str, watchers=watchers, **kwargs)
        except Failure as failure:
            # Transmute failures driven by our CallbackResponder, into auth
            # failures - the command never even ran.
            # TODO: wants to be a hook here for users that desire "override a
            # bad config value for sudo.password" manual input
            # NOTE: as noted in #294 comments, we MAY in future want to update
            # this so run() is given ability to raise AuthFailure on its own.
            # For now that has been judged unnecessary complexity.
            if isinstance(failure.reason, ResponseNotAccepted):
                # NOTE: not bothering with 'reason' here, it's pointless.
                # NOTE: using raise_from(..., None) to suppress Python 3's
                # "helpful" multi-exception output. It's confusing here.
                error = AuthFailure(result=failure.result, prompt=prompt)
                raise_from(error, None)
            # Reraise for any other error so it bubbles up normally.
            else:
                raise
    
    def prompt_for_password(self, prompt, memoize):
        password = getpass(prompt)
        
        if memoize:
            ###NOTE: won't be prompted again because of this
            self.config.sudo.password = password
        
        return password
