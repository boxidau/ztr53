#
# adapted from github.com/Red5d/ztadmin
#

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import requests
import datetime
import json
import ipaddress


class ZT(object):
    def __init__(self, api_key):
        self.api_key = api_key
        self.api_base = "https://my.zerotier.com/api"

    def request(self, path, data=None):
        if not data:
            response = requests.get("{}{}".format(self.api_base, path),
                                headers={'Authorization': 'Bearer {}'.format(self.api_key)})
        else:
            response = requests.post("{}{}".format(self.api_base, path),
                                 headers={'Authorization': 'Bearer {}'.format(self.api_key)},
                                 data=data)

        if response.status_code == 403:
            raise ZeroTierAuthenticationError()

        return response

    def status(self):
        return self.request("/status").json()

    def self(self):
        return self.request("/self").json()

    def user(self):
        return self.request("/user").json()

    def list_networks(self):
        return [Network(self, n) for n in self.request("/network").json()]

    def network(self, nwid):
        network_response = self.request("/network/{}".format(nwid))
        if network_response.status_code == 404:
            raise NetworkNotFoundException()
        return Network(self, network_response.json())

    def list_members(self, nwid):
        return list(self.request("/network/{}/member".format(nwid)).json().keys())

    def member(self, nwid, mid, netActive=[]):
        return Member(self,
                      self.request("/network/{}/member/{}".format(nwid, mid)).json(),
                      netActive)


class NetworkNotFoundException(Exception):
    pass


class ZeroTierAuthenticationError(Exception):
    pass


class Network(object):
    def __init__(self, z, njson):
        self.name = njson['config']['name']
        self.description = njson['description']
        self.id = njson['id']
        self.creationTime = datetime.datetime.fromtimestamp(njson['config']['creationTime'] / float(1000))
        self.private = njson['config']['private']
        self.authorizedMemberCount = njson['config']['authorizedMemberCount']
        self.allowPassiveBridging = njson['config']['allowPassiveBridging']
        self.ipAssignmentPools = njson['config']['ipAssignmentPools']
        try:
            self.routes = njson['config']['routes']
        except KeyError:
            self.routes = njson['config']['ipLocalRoutes']

        self.multicastLimit = njson['config']['multicastLimit']
        self.v4AssignMode = njson['config']['v4AssignMode']
        self.v6AssignMode = njson['config']['v6AssignMode']
        self.relays = njson['config']['relays']
        self.rules = njson['config']['rules']
        self.clock = datetime.datetime.fromtimestamp(njson['config']['clock'] / float(1000))
        self._json = njson
        self._z = z

    def __str__(self):
        return "{} - {}".format(self.id, self.name)

    @property
    def activeMembers(self):
        members = []
        # Get a Member object for each active member of this network.
        for mem in list(self._json['activeMembers'].keys()):
            members.append(self._z.member(self.id, mem, list(self._json['activeMembers'].keys())))

        return members

    @property
    def members(self):
        pass

class Member(object):
    def __init__(self, z, mjson, netActive=None):
        self._json = mjson
        self._z = z
        self.address = mjson['config']['address']
        self.clock = datetime.datetime.fromtimestamp(mjson['config']['clock'] / float(1000))
        self.networkId = mjson['networkId']
        self.nodeId = mjson['nodeId']
        self.identity = mjson['config']['identity']
        self.recentLog = mjson['config']['recentLog']

        # If a list of active network members has been given, check against that to see if this member is active.
        self.online = False
        if netActive and self.nodeId in netActive:
            self.online = True
        elif self.nodeId in list(z.request("/network/{}".format(self.networkId)).json()['activeMembers'].keys()):
            self.online = True

    def __str__(self):
        return json.dumps(self._json, indent=2)

    def save(self, z):
        return z.request("/network/{}/member/{}".format(self.networkId, self.address), data=self._json)

    @property
    def name(self):
        return self._json['name']

    @name.setter
    def name(self, value):
        return self._z.request("/network/{}/member/{}".format(self.networkId, self.address), data={'name': value})
        # self._json['name'] = value

    @property
    def description(self):
        return self._json['description']

    @description.setter
    def description(self, value):
        self._json['description'] = value

    @property
    def activeBridge(self):
        return self._json['config']['activeBridge']

    @activeBridge.setter
    def activeBridge(self, value):
        self._json['config']['activeBridge'] = value

    @property
    def authorized(self):
        return self._json['config']['authorized']

    @authorized.setter
    def authorized(self, value):
        self._json['config']['authorized'] = value

    @property
    def ipAssignments(self):
        return self._json['config']['ipAssignments']

    @ipAssignments.setter
    def ipAssignments(self, value):
        self._json['config']['ipAssignments'] = value

    @property
    def importance(self):
        return self._json['importance']

    @importance.setter
    def importance(self, value):
        self._json['importance'] = value

    @property
    def rfc4193(self):
        return ipaddress.IPv6Address(
            int('fd{}9993{}'.format(self.networkId, self.nodeId), 16)
        )