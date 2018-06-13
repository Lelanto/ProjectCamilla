# -*- coding: utf-8 -*-
import socket
import random
from BeautifulSoup import BeautifulSoup
from logging.handlers import RotatingFileHandler
import time
import logging
import mechanize
import os
import re
import sys
from random import randint
from datetime import datetime, timedelta
from utils import *
from urllib import urlencode
from planet import Planet, Moon
from attack import Attack
from transport_manager import TransportManager
from config import options
from sim import Sim

from selenium import webdriver
import cookielib



socket.setdefaulttimeout(float(options['general']['timeout']))


class Bot(object):

    HEADERS = [('User-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/66.0.3359.181 Safari/537.36')]
    RE_BUILD_REQUEST = re.compile(r"sendBuildRequest\(\'(.*)\', null, 1\)")
    RE_SERVER_TIME = re.compile(r"var serverTime=new Date\((.*)\);var localTime")

    #ship -> ship id on the page
    SHIPS = {
        'lm': '204',
        'hm': '205',
        'cr': '206',
        'ow': '207',
        'pn': '215',
        'bb': '211',
        'ns': '213',
        'gs': '214',
        'lt': '202',
        'dt': '203',
        'cs': '208',
        'rc': '209',
        'ss': '210'
    }

    # mission ids
    MISSIONS = {
        'attack': '1',
        'transport': '3',
        'station': '4',
        'expedition': '15',
        'collect' : '8'
    }

    TARGETS = {
        'planet' : '1',
        'moon' : '3',
        'debris' : '2'
    }

    SPEEDS = {
        100: '10',
        90: '9',
        80: '8',
        70: '7',
        60: '6',
        50: '5',
        40: '4',
        30: '3',
        20: '2',
        10: '1'
    }
    
    def __init__(self, username=None, password=None, server=None):
        self.server = server
        self.username = username
        self.password = password
        self.logged_in = False
        
        self._prepare_logger()

        n = 1
        self.farm_no = []
        self.bn_farms = 'farms_';
        self. bn_from_planet = 'from_planet_';
        loop = True;
        while loop:
            try:
                self.logger.info("Inizio")
                farms = options['farming'][self.bn_farms + str(n)].split(' ')
                self.farm_no.append((randint(0, len(farms) - 1) if farms else 0))
                from_planet = options['farming'][self.bn_from_planet + str(n)]
                self.logger.info("Per il pianeta" +from_planet+ " inizio dalla farm n: " + str(self.farm_no[n-1]))
                n += 1
            except Exception as e:
                loop = False

        self.MAIN_URL =  'https://' + self.server + '/game/index.php'
        self.PAGES = {
            'main':        self.MAIN_URL + '?page=overview',
            'resources':   self.MAIN_URL + '?page=resources',
            'station':     self.MAIN_URL + '?page=station',
            'research':    self.MAIN_URL + '?page=research',
            'shipyard':    self.MAIN_URL + '?page=shipyard',
            'defense':     self.MAIN_URL + '?page=defense',
            'fleet':       self.MAIN_URL + '?page=fleet1',
            'galaxy':      self.MAIN_URL + '?page=galaxy',
            'galaxyCnt':   self.MAIN_URL + '?page=galaxyContent',
            'events':      self.MAIN_URL + '?page=eventList',
            'messages':    self.MAIN_URL + '?page=messages',
        }
        self.planets = []
        self.moons = []
        self.active_attacks = []

        self.fleet_slots = 0
        self.active_fleets = 0

        self.server_time = self.local_time = datetime.now()
        self.time_diff = 0
        self.emergency_sms_sent = False
        self.transport_manager = TransportManager()
        self.sim = Sim()

    def _get_url(self, page, planet=None):
        url = self.PAGES[page]
        if planet is not None:
            url += '&cp=%s' % planet.id
        return url
        
    def _prepare_logger(self):
        self.logger = logging.getLogger("mechanize")
        fh = RotatingFileHandler('bot.log', maxBytes=100000, backupCount=5)
        sh = logging.StreamHandler()
        fmt = logging.Formatter(fmt='%(asctime)s %(levelname)s %(message)s',
                                datefmt='%m-%d, %H:%M:%S')
        fh.setFormatter(fmt)
        sh.setFormatter(fmt)
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(fh)
        self.logger.addHandler(sh)
        

    def _parse_build_url(self, js):
        """
        convert: `sendBuildRequest('url', null, 1)`; into: `url`
        """
        return self.RE_BUILD_REQUEST.findall(js)[0]

    def _parse_server_time(self, content):
        return self.RE_SERVER_TIME.findall(content)[0]
    
    def get_mother(self):
        for p in self.planets:
            if p.mother:
                return p
        return p[0] if self.planets else None

    def get_closest_planet(self, p):
        def min_dist(p, d):
            return d
        _, d, _ = p.split(":")
        return sorted([(planet, planet.get_distance(p)) for planet in self.planets], 
            key=lambda x: x[1])[0][0]


    def find_planet(self, name=None, coords=None, id=None, is_moon=None):
        if is_moon:
            planets = self.moons
        else:
            planets = self.planets
        for p in planets:
            if name == p.name or coords == p.coords or id == p.id:
                return p

    def get_safe_planet(self, planet):
        '''
        Get first planet which is not under attack and isn't `planet`
        '''
        unsafe_planets = [a.planet for a in self.active_attacks]
        for p in self.planets:
            if not p in unsafe_planets and p != planet:
                return p
        # no safe planets! go to mother
        return self.planets[0]

    def login(self, username=None, password=None, server=None):
        username = username or self.username
        password = password or self.password
        server = server or self.server

        try:
            resp = self.br.open(self.MAIN_URL, timeout=10)
            soup = BeautifulSoup(resp)
        except:
            return False
        
        alert = soup.find(id='attack_alert')

        # no redirect on main page == user logged in
        if resp.geturl().startswith(self.server) and alert:
            self.logged_in = True
            self.logger.info('Logged as: %s' % username)
            return True
        
        self.logger.info('Logging in..')
        self.br.select_form(name='loginForm')

        self.br.form['uni'] = [server]
        self.br.form['login'] = username
        self.br.form['pass'] = password
        self.br.submit()

        if self.br.geturl().startswith(self.MAIN_URL):
            self.logged_in = True
            self.logger.info('Logged as: %s' % username)
            return True
        else:
            self.logged_in = False
            self.logger.error('Login failed!')
            return False

    def login_lobby(self, username=None, password=None, server=None):
        username = username or self.username
        password = password or self.password
        server = server or self.server
        player_id = options['credentials']['player_id']
        number = server[1:4]
        try:
            driver = webdriver.Chrome()
            driver.get("https://it.ogame.gameforge.com")

            # Chiudo banner
            driver.find_element_by_link_text("x").click()

            # Vado sulla Login Form
            driver.find_element_by_link_text("Login").click()

            # Immetto Credenziali
            usernameLogin = driver.find_element_by_id("usernameLogin")
            passwordLogin = driver.find_element_by_id("passwordLogin")

            usernameLogin.send_keys(username)
            passwordLogin.send_keys(password)

            # Clicco su login
            driver.find_element_by_id("loginSubmit").click()
            time.sleep(2)

            # Recupero URL login
            driver.get("https://lobby-api.ogame.gameforge.com/users/me/loginLink?id=" + player_id + "&server[language]=it&server[number]= " + number)
            time.sleep(2)

            # Richiamo il login
            html = driver.page_source
            soup = BeautifulSoup(html)
            url = 'https://' + server + '/game/lobbylogin.php?' + soup.find('pre').text.split('?')[1].replace('"}', '').replace('&amp;', '&')
            driver.get(url)

            # Passo i cookie e la sessione a mechanize
            cookie = driver.get_cookies()
            cj = cookielib.LWPCookieJar()

            for s_cookie in cookie:
                cj.set_cookie(cookielib.Cookie(version=0, name=s_cookie['name'], value=s_cookie['value'], port='80',
                                               port_specified=False, domain=s_cookie['domain'], domain_specified=True,
                                               domain_initial_dot=False, path=s_cookie['path'], path_specified=True,
                                               secure=s_cookie['secure'], expires=None, discard=False,
                                               comment=None, comment_url=None, rest=None, rfc2109=False))

            # Instantiate a Browser and set the cookies
            self.br = mechanize.Browser()
            self.br.set_cookiejar(cj)
            self.br.set_handle_equiv(True)
            self.br.set_handle_redirect(True)
            self.br.set_handle_referer(True)
            self.br.set_handle_robots(False)
            self.br.addheaders = self.HEADERS
        except:
            return False

        return True

    def calc_time(self, resp):
        try:
            y, mo, d, h, mi, sec = map(int, self._parse_server_time(resp).split(','))
        except:
            self.logger.error('Exception while calculating time')
        else:
            self.local_time = n = datetime.now()
            self.server_time = datetime(n.year, n.month, n.day, h, mi, sec)
            self.time_diff = self.server_time - self.local_time

            self.logger.info('Server time: %s, local time: %s' % \
                (self.server_time, self.local_time))

    def fetch_planets(self):
        self.logger.info('Fetching planets..')

        resp = self.br.open(self.PAGES['main']).read()

        self.calc_time(resp)

        soup = BeautifulSoup(resp)
        self.planets = []
        self.moons = []

        try:
            for i, c in enumerate(soup.findAll('a', 'planetlink')):
                name = c.find('span', 'planet-name').text
                coords = c.find('span', 'planet-koords').text[1:-1]
                url = c.get('href')
                p_id = int(c.parent.get('id').split('-')[1])
                construct_mode = len(c.parent.findAll('a', 'constructionIcon')) != 0
                p = Planet(p_id, name, coords, url, construct_mode)
                if i == 0:
                    p.mother = True
                self.planets.append(p)

                #check if planet has moon
                moon = c.parent.find('a', 'moonlink')
                if moon and 'moonlink' in moon['class']:
                    url = moon.get('href')
                    m_id = url.split('cp=')[1]
                    m = Moon(m_id, coords, url)
                    self.moons.append(m)
        except:
            self.logger.exception('Exception while fetching planets')
        else:
            self.check_attacks(soup)

    def handle_planets(self):
        self.fetch_planets()

        for p in iter(self.planets):
            self.update_planet_info(p)
            self.update_planet_fleet(p)
        for m in iter(self.moons):
            self.update_planet_info(m)
            self.update_planet_fleet(m)

    def update_planet_fleet(self, planet):
        resp = self.br.open(self._get_url('fleet', planet))
        soup = BeautifulSoup(resp)
        ships = {}
        for k, v in self.SHIPS.iteritems():
            available = 0
            try:
                s = soup.find(id='button' + v)
                available = int(s.find('span', 'textlabel').nextSibling.replace('.', ''))
            except:
                available = 0
            ships[k] = available

        #self.logger.info('Updating %s fleet' % planet)
        #self.logger.info('%s' % fleet)
        planet.ships = ships

    def update_planet_resources_farmed(self,planet,baseMetal,baseCrystal,baseDeuterium):
        # Seleziono pianeta di attacco
        resp = self.br.open(self._get_url('fleet',planet))
        soup = BeautifulSoup(resp)
        try:
            metal = int(soup.find(id='resources_metal').text.replace('.',''))-baseMetal
            crystal = int(soup.find(id='resources_crystal').text.replace('.',''))-baseCrystal
            deuterium = int(soup.find(id='resources_deuterium').text.replace('.',''))-baseDeuterium
            totalResoucesFarmed= metal+crystal+deuterium
        except:
            self.logger.exception('Exception while updating resources info')
        self.logger.info('Pianeta: '+str(planet.coords)+' Metallo: ' + str(metal) + ' - Cristallo: '+str(crystal)+ ' - Deuterio: '+ str(deuterium))
        self.logger.info('Pianeta: '+str(planet.coords)+' Totale risorse farmate: ' + str(totalResoucesFarmed))

    def update_planet_info(self, planet):
        in_construction_mode = False
        resp = self.br.open(self._get_url('resources', planet))
        soup = BeautifulSoup(resp)

        try:
            metal = int(soup.find(id='resources_metal').text.replace('.',''))
            planet.resources['metal'] = metal
            crystal = int(soup.find(id='resources_crystal').text.replace('.',''))
            planet.resources['crystal'] = crystal
            deuterium = int(soup.find(id='resources_deuterium').text.replace('.',''))
            planet.resources['deuterium'] = deuterium
            energy = int(soup.find(id='resources_energy').text.replace('.',''))
            planet.resources['energy'] = energy
        except:
            self.logger.exception('Exception while updating resources info')
        else:
            self.logger.info('Updating resources info for %s:' % planet)
            s = 'metal - %(metal)s, crystal - %(crystal)s, deuterium - %(deuterium)s'
            self.logger.info(s % planet.resources)
        if planet.is_moon():
            return
        try:
            buildingList = soup.find(id='building')
            buildings = ('metalMine', 'crystalMine', 'deuteriumMine', 'solarPlant',
                'fusionPlant', 'solarSatellite'
            )
            for building, b in zip(buildings, buildingList.findAll('li')):
                can_build = 'on' in b.get('class')
                fb = b.find('a', 'fastBuild')
                build_url = fb.get('onclick') if fb else ''
                if build_url:
                    build_url = self._parse_build_url(build_url)
                try:
                    level = int(b.find('span', 'textlabel').nextSibling)
                except AttributeError:
                    try:
                        level = int(b.find('span', 'level').text)
                    except:
                        pass
                suff_energy = planet.resources['energy'] - self.sim.upgrade_energy_cost(building, level+1) > 0
                res = dict(
                    level=level, 
                    can_build=can_build,
                    build_url=build_url,
                    sufficient_energy=suff_energy
                )

                planet.buildings[building] = res

            if buildingList.find('div', 'construction'):
                in_construction_mode = True
        except:
            self.logger.exception('Exception while updating buildings info')
            return False
        else:
            self.logger.info('%s buildings were updated' % planet)
        if not in_construction_mode:
            text, url = planet.get_mine_to_upgrade()
            if url:
                self.logger.info('Building upgrade on %s: %s'% (planet, text))
                self.br.open(url)
                planet.in_construction_mode = True
                #let now transport manager to clear building queue
                self.transport_manager.update_building(planet)
        else:
            self.logger.info('Building queue is not empty')
        return True

    def transport_resources(self):
        tasks = self.transport_manager.find_dest_planet(self.planets)
        if tasks is None:
            return False
        self.logger.info(self.transport_manager.get_summary())
        for task in iter(tasks):
            self.logger.info('Transport attempt from: %s, to: %s with resources %s' \
                % (task['from'], task['where'], task['resources']))
            result = self.send_fleet(
                task['from'], 
                task['where'].coords, 
                fleet=task['from'].get_fleet_for_resources(task['resources']),
                resources=task['resources'],
                mission='transport'
            )
            if result:
                self.transport_manager.update_sent_resources(task['resources'])
                self.logger.info('Resources sent: %s, resources needed: %s' \
                    % (task['resources'], self.transport_manager.get_resources_needed()))

        return True

    def build_defense(self, planet):
        """
        Build defense for all resources on the planet
        1. plasma
        2. gauss
        3. heavy cannon
        4. light cannon
        5. rocket launcher
        """
        url = self._get_url('defense', planet)
        resp = self.br.open(url)
        for t in ('406', '404', '403', '402', '401'):
            self.br.select_form(name='form')
            self.br.form.new_control('text','menge',{'value':'100'})
            self.br.form.fixup()
            self.br['menge'] = '100'

            self.br.form.new_control('text','type',{'value':t})
            self.br.form.fixup()
            self.br['type'] = t

            self.br.form.new_control('text','modus',{'value':'1'})
            self.br.form.fixup()
            self.br['modus'] = '1'

            self.br.submit()

    def get_player_status(self, destination, origin_planet=None):
        if not destination:
            return
            
        status = {}
        origin_planet = origin_planet or self.get_closest_planet(destination)
        galaxy, system, position = destination.split(':')

        url = self._get_url('galaxyCnt', origin_planet)
        data = urlencode({'galaxy': galaxy, 'system': system})
        resp = self.br.open(url, data=data)
        soup = BeautifulSoup(resp)

        soup.find(id='galaxytable')
        planets = soup.findAll('tr', {'class': 'row'})
        target_planet = planets[int(position)-1]
        name_el = target_planet.find('td', 'playername')
        status['name'] = name_el.find('span').text

        status['inactive'] = 'inactive' in name_el.get('class', '')
        return status

    def find_inactive_nearby(self, planet, radius=15):

        self.logger.info("Searching idlers near %s in radius %s" 
            % (planet, radius))

        nearby_systems = planet.get_nearby_systems(radius)
        idlers = []

        for system in nearby_systems:
            galaxy, system = system.split(":")
            url = self._get_url('galaxyCnt', planet)
            data = urlencode({'galaxy': galaxy, 'system': system})
            resp = self.br.open(url, data=data)
            soup = BeautifulSoup(resp)

            galaxy_el = soup.find(id='galaxytable')
            planets = galaxy_el.findAll('tr', {'class': 'row'})
            for pl in planets:
                name_el = pl.find('td', 'playername')
                debris_el = pl.find('td', 'debris')
                inactive = 'inactive' in name_el.get('class', '')
                debris_not_found = 'js_no_action' in debris_el.get('class', '')
                if not inactive or not debris_not_found:
                    continue
                position = pl.find('td', 'position').text
                coords = "%s:%s:%s" % (galaxy, system, position)
                player_id = name_el.find('a').get('rel')

                player_info = soup.find(id=player_id)
                rank_el = player_info.find('li', 'rank')

                if not rank_el:
                    continue

                rank = int(rank_el.find('a').text)
                if rank > 4000 or rank < 900:
                    continue

                idlers.append(coords)
                time.sleep(2)

        return idlers

    def find_inactives(self):

        inactives = []
        for p in self.planets:
            try:
                idlers = self.find_inactive_nearby(p)
                self.logger.info(" ".join(idlers))
                inactives.extend(idlers)
            except Exception as e:
                self.logger.exception(e)
                continue
            time.sleep(5)

        self.logger.info(" ".join(inactives))
        self.inactives = list(set(inactives))
        self.logger.info(inactives)

    def send_fleet(self, origin_planet, destination, fleet={}, resources={},
            mission='attack', target='planet', speed=None):

        if origin_planet.coords == destination:
            self.logger.error('Cannot send fleet to the same planet')
            return False

        self.logger.info('Sending fleet from %s to %s (%s)' \
            % (origin_planet, destination, mission))

        try:
            resp = self.br.open(self._get_url('fleet', origin_planet))
            try:
                self.br.select_form(name='shipsChosen')
            except mechanize.FormNotFoundError:
                self.logger.info('No available ships on the planet')
                return False

            soup = BeautifulSoup(resp)
            for ship, num in fleet.iteritems():
                s = soup.find(id='button' + self.SHIPS[ship])
                num = int(num)
                try:
                    available = int(s.find('span', 'textlabel').nextSibling.replace('.', ''))
                except:
                    available = 0
                if available < num and mission in ('attack', 'expedition'):
                    self.logger.info('No available ships to send')
                    return False
                if num > 0:
                    self.br.form['am' + self.SHIPS[ship]] = str(num)

            self.miniSleep()
            self.br.submit()

            try:
                self.br.select_form(name='details')
            except mechanize.FormNotFoundError:
                self.logger.info('No available ships on the planet')
                return False

            galaxy, system, position = destination.split(':')
            self.br['galaxy'] = galaxy
            self.br['system'] = system
            self.br['position'] = position
            self.br.form.find_control("type").readonly = False
            self.br['type'] = self.TARGETS[target]
            self.br.form.find_control("speed").readonly = False
            self.br['speed'] = speed

            self.miniSleep()
            self.br.submit()

            self.br.select_form(name='sendForm')
            self.br.form.find_control("mission").readonly = False
            self.br.form['mission'] = self.MISSIONS[mission]
            if 'metal' in resources:
                self.br.form['metal'] = str(resources['metal'])
            if 'crystal' in resources:
                self.br.form['crystal'] = str(resources['crystal'])
            if 'deuterium' in resources:
                self.br.form['deuterium'] = str(resources['deuterium'])

            self.miniSleep()
            self.br.submit()
            self.miniSleep()
        except Exception as e:
            self.logger.exception(e)
            return False

        return True

    def send_message(self, url, player, subject, message):
        self.logger.info('Sending message to %s: %s' % (player, message))
        self.br.open(url)
        self.br.select_form(nr=0)
        self.br.form['betreff'] = subject
        self.br.form['text'] = message
        self.br.submit()

    def send_sms(self, msg):
        from smsapigateway import SMSAPIGateway
        try:
            SMSAPIGateway().send(msg)
        except Exception as e:
            self.logger.exception(str(e))


    def handle_attacks(self):
        attack_opts = options['attack']
        send_sms = bool(options['sms']['send_sms'])

        for a in self.active_attacks:
            if a.is_dangerous():
                self.logger.info('Handling attack: %s' % a)
                if not a.planet.is_moon():
                    self.build_defense(a.planet)
                if send_sms and not a.sms_sent:
                    self.send_sms(a.get_sms_text())
                    a.sms_sent = True
                if send_sms and not a.message_sent:
                    self.send_message(a.message_url, a.player, attack_opts['message_topic'], 
                        a.get_random_message())
                    a.message_sent = True
                self.fleet_save(a.planet)

    def check_attacks(self, soup):
        chatIdTelegram = options['credentials']['chat_id_telegram']
        botTelegram = options['credentials']['bot_telegram']
        alert = soup.find(id='attack_alert')
        if not alert:
            self.logger.exception('Check attack failed')
            return
        if 'noAttack' in alert.get('class', ''):
            self.logger.info('No attacks')
            self.active_attacks = []
        else:
            self.logger.info('ATTACK!')
            resp = self.br.open(self.PAGES['events'])
            soup = BeautifulSoup(resp)
            hostile = False
            attack_id=0
            url = 'https://api.telegram.org/' + str(botTelegram) + '/sendMessage?'
            text = ''
            arrivalTime = ''
            originCoords = []
            destCoords = ''
            detailsFleet = []
            player = []
            attackNew = False
            try:
                for tr in soup.findAll('tr'):
                    countDown = tr.find('td', 'countDown')
                    if countDown and 'hostile' in countDown.get('class', ''):
                        hostile = True
                        # First: check if attack was noticed
                        if tr.get('id'):
                            attack_id = tr.get('id').split('-')[1]
                        elif countDown.get('id'):
                            attack_id = countDown.get('id').split('-')[2]
                        if not attack_id or attack_id in [a.id for a in self.active_attacks]:
                            continue
                        if tr.get('class').split(' ')[0] == 'allianceAttack':
                            typeAttack = 'ATTACCO FEDERATO'
                        else:
                            typeAttack = 'ATTACCO'
                        if str(typeAttack) != str('ATTACCO FEDERATO') and tr.get('class').split(' ')[0]!= 'partnerInfo':
                            attackNew = True
                            try:
                                # Attack first discovered: save attack info
                                arrivalTime = tr.find('td', 'arrivalTime').text.split(' ')[0]
                                coordsOrigin = tr.find('td', 'coordsOrigin')
                                if coordsOrigin:
                                    if coordsOrigin.find('a'):
                                        originCoords.append(coordsOrigin.find('a').text.strip()[1:-1])
                                destCoords = tr.find('td', 'destCoords')
                                if destCoords:
                                    destCoords = destCoords.find('a').text.strip()[1:-1]
                                detailsFleet.append(tr.find('td', 'detailsFleet').span.text.replace('.', ''))
                                player.append(tr.find('td', 'sendMail').find('a').get('title'))
                            except Exception as e:
                                self.logger.exception(e)
                        elif typeAttack == 'ATTACCO FEDERATO' or tr.get('class').split(' ')[0]== 'partnerInfo':
                            if tr.get('class').split(' ')[0] == 'partnerInfo':
                                coordsOrigin = tr.find('td', 'coordsOrigin')
                                if coordsOrigin:
                                    if coordsOrigin.find('a'):
                                        originCoords.append(coordsOrigin.find('a').text.strip())
                                player.append(tr.find('td', 'sendMail').find('a').get('title'))
                                detailsFleet.append(tr.find('td', 'detailsFleet').span.text.replace('.', ''))
                            else:
                                attackNew = True
                                arrivalTime = tr.find('td', 'arrivalTime').text.split(' ')[0]
                                destCoords = tr.find('td', 'destCoords')
                                if destCoords:
                                    destCoords = destCoords.find('a').text.strip()[1:-1]
                                detailsFleet = tr.find('td', 'detailsFleet').span.text.replace('.', '')

                    if attackNew:
                        text = text + '\n\n' + str(typeAttack) + ' IN CORSO\n' \
                    'Orario di arrivo: ' + str(arrivalTime) + '\n' \
                    'Coordinate di arrivo: ' + str(destCoords) + '\n'
                    for i in range(0,len(player),1):
                        text = text + '\t\t\t\t\tGIOCATORE: ' + str(player[i]) + '\n' \
                        '\t\t\t\t\tCoordinate di partenza: ' + str(originCoords[i]) + '\n' \
                        '\t\t\t\t\tNumero navi in arrivo: ' + str(detailsFleet[i]) + '\n'
                    arrivalTime = ''
                    coordsOrigin = []
                    destCoords = ''
                    detailsFleet = []
                    player = []
                    attackNew = False
                if chatIdTelegram != '':
                    data = urlencode({'chat_id': chatIdTelegram, 'text': text})
                    self.br.open(url, data=data)
                if not hostile:
                    self.active_attacks = []
            except Exception as e:
                self.logger.exception(e)
                
    def fleet_save(self, p):
        if not p.has_ships():
            return
        fleet = p.ships
        #recyclers are staying!
        #fleet['rc'] = 0
        self.logger.info('Making fleet save from %s' % p)
        self.send_fleet(p, 
            self.get_safe_planet(p).coords, 
            fleet=fleet, 
            mission='station',
            speed=10,
            resources={'metal': p.resources['metal']+500,
                       'crystal': p.resources['crystal']+500,
                       'deuterium': p.resources['deuterium']+500})

    def collect_debris(self, p):
        if not p.has_ships():
            return
        self.logger.info('Collecting debris from %s using %s recyclers' % (p, p.ships['rc']))
        self.send_fleet(p, 
            p.coords, 
            fleet={'rc':p.ships['rc']},
            mission='collect',
            target='debris')

    def send_expedition(self):
        expedition = options['expedition']
        planets = expedition['planets'].split(' ')
        random.shuffle(planets)
        for coords in planets[:3]:
            planet = self.find_planet(coords=coords)
            if planet:
                galaxy, system, position = planet.coords.split(':')
                expedition_coords = '%s:%s:16' % (galaxy, system)
                self.send_fleet(planet, expedition_coords,
                    fleet={expedition['ships_kind']:expedition['ships_number']}, 
                    mission='expedition')

    #
    # Invio farmata di sonde
    #
    def farm(self):
        # Carico settings
        ships_kind = options['farming']['ships_kind']
        ships_number = options['farming']['ships_number']
        speed = options['farming']['ships_speed']

        # Ciclo sui pianeti da farmare
        n = 1

        farms = options['farming'][self.bn_farms + str(n)].split(' ')
        from_planet = options['farming'][self.bn_from_planet + str(n)]
        loop = True;
        while loop:
            # Seleziono pianeta di attacco
            planet = self.find_planet(coords=from_planet, is_moon=True)
            self.update_planet_resources_farmed(planet,0,0,100000)
            # Controllo che ci siano farm
            l = len(farms)
            if not(l == 0 or not farms[0]):

                # Seleziono la prossima farm da attaccare
                farm = farms[self.farm_no[n-1] % l]

                # Invio attacchi finche ci sono navi
                while self.send_fleet(
                           planet,
                           farm,
                           fleet={ships_kind:ships_number},
                           speed=speed):
                    self.farm_no[n-1] += 1
                    farm = farms[self.farm_no[n-1] % l]

            n += 1

            try:
               farms = options['farming'][self.bn_farms + str(n)].split(' ')
               from_planet = options['farming'][self.bn_from_planet + str(n)]
            except Exception as e:
                loop = False



    def sleep(self):
        sleep_options = options['general']
        min = int(sleep_options['seed']) - randint(0,int(sleep_options['check_interval']))
        max = int(sleep_options['seed']) + randint(0,int(sleep_options['check_interval']))
        sleep_time = randint(min, max)
        self.logger.info('Sleeping for %s secs' % sleep_time)
        if self.active_attacks:
            sleep_time = 60
        time.sleep(sleep_time)

    def miniSleep(self):
        mini_sleep_time = randint(400, 2500) / 1000
        time.sleep(mini_sleep_time)

    def stop(self):
        self.logger.info('Stopping bot')
        os.unlink(self.pidfile)
        
    def start(self):
        self.logger.info('Starting bot')
        self.pid = str(os.getpid())
        self.pidfile = 'bot.pid'
        file(self.pidfile, 'w').write(self.pid)
        
        # Semplificato con la sola esecuzione del Farming Bot
        if self.login_lobby():
            try:

                while True:
                    self.fetch_planets()
                    self.farm()
                    self.sleep()

            except Exception as e:
                self.logger.exception(e)
        else:
            self.logger.error('Login failed!')


    
if __name__ == "__main__":
    credentials = options['credentials']
    bot = Bot(credentials['username'], credentials['password'], credentials['server'])
    bot.start()
