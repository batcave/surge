from invoke.watchers import Responder


class CallbackResponder(Responder):
    def submit(self, stream):
        pass
        ###COPY: code largely stolen from invoke:invoke.watchers:FailingResponder.submit
        
        # Behave like regular Responder initially
        response = super().submit(stream)
        
        if callable(response):
            response = response()
        
        # Also check stream for our failure sentinel
        failed = self.pattern_matches(stream, self.sentinel, "failure_index")
        
        # Error out if we seem to have failed after a previous response.
        if self.tried and failed:
            err = f'Auto-response to r"{self.pattern}" failed with {self.sentinel!r}!'
            
            raise ResponseNotAccepted(err)
        
        # Once we see that we had a response, take note
        if response:
            self.tried = True
        
        # Again, behave regularly by default.
        return response
