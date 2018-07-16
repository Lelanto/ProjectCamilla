from BeautifulSoup import BeautifulSoup


class Bot_unuserd_code(object):

    def get_closest_planet(self, p):
        _, d, _ = p.split(":")
        return sorted([(planet, planet.get_distance(p)) for planet in self.planets],
                      key=lambda x: x[1])[0][0]

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

    def fleet_save(self, p):
        if not p.has_ships():
            return
        fleet = p.ships
        # recyclers are staying!
        # fleet['rc'] = 0
        self.logger.info('Making fleet save from %s' % p)
        self.send_fleet(p,
                        self.get_safe_planet(p).coords,
                        fleet=fleet,
                        mission='station',
                        speed=10,
                        resources={'metal': p.resources['metal'] + 500,
                                   'crystal': p.resources['crystal'] + 500,
                                   'deuterium': p.resources['deuterium'] + 500})

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
        target_planet = planets[int(position) - 1]
        name_el = target_planet.find('td', 'playername')
        status['name'] = name_el.find('span').text
        status['inactive'] = 'inactive' in name_el.get('class', '')
        return status


    def find_inactive_nearby(self, planet, radius=15):
        self.logger.info("Searching idlers near %s in radius %s" % (planet, radius))
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
            self.br.form.new_control('text', 'menge', {'value': '100'})
            self.br.form.fixup()
            self.br['menge'] = '100'

            self.br.form.new_control('text', 'type', {'value': t})
            self.br.form.fixup()
            self.br['type'] = t

            self.br.form.new_control('text', 'modus', {'value': '1'})
            self.br.form.fixup()
            self.br['modus'] = '1'

            self.br.submit()

    def update_planet_resources(self, planet):
        self.miniSleep()
        try:
            resp = self.br.open(self._get_url('resources', planet))
            soup = BeautifulSoup(resp)
            metal = int(soup.find(id='resources_metal').text.replace('.', ''))
            self.RESOURCESTOSEND['metal']=metal
            crystal = int(soup.find(id='resources_crystal').text.replace('.', ''))
            self.RESOURCESTOSEND['crystal'] = crystal
            deuterium = int(soup.find(id='resources_deuterium').text.replace('.', ''))
            self.RESOURCESTOSEND['deuterium'] = deuterium
        except:
            self.logger.exception('Exception while updating resources info')

        #
        # Matteo: Codice commentato perche inutile
        #
        # if planet.is_moon():
        #     return
        # try:
        #     buildingList = soup.find(id='building')
        #     buildings = ('metalMine', 'crystalMine', 'deuteriumMine', 'solarPlant',
        #                  'fusionPlant', 'solarSatellite'
        #                  )
        #     for building, b in zip(buildings, buildingList.findAll('li')):
        #         can_build = 'on' in b.get('class')
        #         fb = b.find('a', 'fastBuild')
        #         build_url = fb.get('onclick') if fb else ''
        #         if build_url:
        #             build_url = self._parse_build_url(build_url)
        #         try:
        #             level = int(b.find('span', 'textlabel').nextSibling)
        #         except AttributeError:
        #             try:
        #                 level = int(b.find('span', 'level').text)
        #             except:
        #                 pass
        #         suff_energy = planet.resources['energy'] - self.sim.upgrade_energy_cost(building, level + 1) > 0
        #         res = dict(
        #             level=level,
        #             can_build=can_build,
        #             build_url=build_url,
        #             sufficient_energy=suff_energy
        #         )
        #
        #         planet.buildings[building] = res
        #
        #     if buildingList.find('div', 'construction'):
        #         in_construction_mode = True
        # except:
        #     self.logger.exception('Exception while updating buildings info')
        #     return False
        # else:
        #     self.logger.info('%s buildings were updated' % planet)
        # if not in_construction_mode:
        #     text, url = planet.get_mine_to_upgrade()
        #     if url:
        #         self.logger.info('Building upgrade on %s: %s' % (planet, text))
        #         self.br.open(url)
        #         planet.in_construction_mode = True
        #         # let now transport manager to clear building queue
        #         self.transport_manager.update_building(planet)
        # else:
        #     self.logger.info('Building queue is not empty')

        return True