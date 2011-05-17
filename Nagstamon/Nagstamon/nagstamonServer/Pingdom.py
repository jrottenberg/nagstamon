# encoding: utf-8
import pingdomapi
import datetime
import time
import traceback
import base64

import nagstamonActions
from nagstamonObjects import *

from Generic import GenericServer


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
                        appkey=self.nagios_url).method("checks")

            print "# RESULT:", len(all_status['checks'])
            for check in  all_status['checks']:
                # "pp" :
                # {'status': 'up',
                #  'lasttesttime': 1305614987,
                #  'name': 'zzz-tester',
                #  'created': 1305314210,
                #  'lasterrortime': 1305324047,
                #  'resolution': 1,
                #  'lastresponsetime': 311,
                #  'hostname': 'google.com',
                #  'type': 'http',
                #  'id': 344985}

                # pp.hostname --> n.host        # we have one hostname
                # pp.name     --> n.service     # that can have multiple checks
                self.new_hosts[check["hostname"]] = GenericHost()
                self.new_hosts[check["hostname"]].name = check["hostname"]
                # states come in lower case from pingdom
                self.new_hosts[check["hostname"]].status = check["status"].upper()
                self.new_hosts[check["hostname"]].last_check = check["lasttesttime"]
                self.new_hosts[check["hostname"]].status_information = check["lastresponsetime"]

                self.new_hosts[check["hostname"]].services[check["name"]] = GenericService()
                self.new_hosts[check["hostname"]].services[check["name"]].host = check["hostname"]
                self.new_hosts[check["hostname"]].services[check["name"]].name = check["name"]
                # states come in lower case from Opsview
                self.new_hosts[check["hostname"]].services[check["name"]].status = check["status"].upper()
                self.new_hosts[check["hostname"]].services[check["name"]].last_check = check["lasttesttime"]
                self.new_hosts[check["hostname"]].services[check["name"]].attempt = "1/5"
        except:
            # set checking flag back to False
            self.isChecking = False
            result, error = self.Error(sys.exc_info())
            return Result(result=result, error=error)

        #dummy return in case all is OK
        return Result()
