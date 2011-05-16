# encoding: utf-8
import pingdom
import cookielib
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


    # Put the apikey in the server url
    def init_HTTP(self):      
        pingdom.Pingdom(username=self.get_username(), password=self.get_password(), appkey=self.nagios_url)


    def _get_status(self):
        """
        Get status from Pingdom
        """
        global result

        try:
            result = self.pingdom_connection.method("checks", "GET")
            htobj, error = result.result, result.error
         
            print "RESULT:", result.result, "\nERROR---->:", result.error
            





        except Exception, err:
            print err
