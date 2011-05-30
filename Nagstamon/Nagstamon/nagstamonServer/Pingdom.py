# encoding: utf-8
import pingdomapi
import datetime
import time
import traceback
import base64

import nagstamonActions
from nagstamonObjects import *

from Generic import GenericServer

# http://www.pingdom.com/services/api-documentation-rest/#ResourceChecks
# Change it if you know what you are doing
# ie : you  shouldn't  have to
pingdom_apikey = "tn3ee3eueg1ug6o480n8mr23bv0r8k66"


class PingdomServer(GenericServer):
    """
       special treatment for pingdom RESTful based API
    """

    TYPE = 'Pingdom'

    # Put the apikey in the server url (until we have a better field name)
    def init_HTTP(self):
        self.Debug("username: ", self.get_username())
        self.Debug("password: ", self.get_password())

    def _get_status(self):
        """
        Get status from Pingdom
        """
        global result
        try:
            all_status = pingdomapi.Pingdom(username=self.get_username(),
                        password=self.get_password(),
                        appkey=pingdom_apikey).method("checks")

            print "# RESULT: %s checks", len(all_status['checks'])
            for c in  all_status['checks']:
                # pp.hostname --> n.host        # we have one hostname
                # pp.name     --> n.service     # that can have multiple checks
                self.new_hosts[c["hostname"]] = GenericHost()
                self.new_hosts[c["hostname"]].name = c["hostname"]
                # states come in lower case from pingdom
                self.new_hosts[c["hostname"]].status = c["status"].upper()
                self.new_hosts[c["hostname"]].last_check = c["lasttesttime"]
                self.new_hosts[c["hostname"]].status_information = c["lastresponsetime"]

                self.new_hosts[c["hostname"]].services[c["name"]] = GenericService()
                self.new_hosts[c["hostname"]].services[c["name"]].host = c["hostname"]
                self.new_hosts[c["hostname"]].services[c["name"]].name = c["name"]
                # states come in lower case from pingdom
                self.new_hosts[c["hostname"]].services[c["name"]].status = c["status"].upper()
                self.new_hosts[c["hostname"]].services[c["name"]].last_check = c["lasttesttime"]
                self.new_hosts[c["hostname"]].services[c["name"]].attempt = "1/5"
        except:
            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)

        #dummy return in case all is OK
        return Result()
