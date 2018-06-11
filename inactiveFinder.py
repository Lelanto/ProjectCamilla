import logging
import mechanize
from config import options
from logging.handlers import RotatingFileHandler
from lxml import etree

from planet import Planet
from player import Player


class InactiveFinder(object):
    HEADERS = [('User-agent','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/66.0.3359.181 Safari/537.36')]

    def __init__(self):

        self._prepare_logger()
        self._prepare_browser()

        self.MAIN_URL = 'https://' + options['credentials']['server']
        self.PAGES = {
            'galaxy': self.MAIN_URL + '/api/universe.xml',
            'players': self.MAIN_URL + '/api/players.xml',
            'general': self.MAIN_URL + '/api/highscore.xml?category=1&type=0',
            'military': self.MAIN_URL + '/api/highscore.xml?category=1&type=3',
        }

    def _prepare_logger( self ):
        self.logger = logging.getLogger("mechanize")
        fh = RotatingFileHandler('inactveFinder.log', maxBytes=100000, backupCount=5)
        sh = logging.StreamHandler()
        fmt = logging.Formatter(fmt='%(asctime)s %(levelname)s %(message)s',
                                datefmt='%m-%d, %H:%M:%S')
        fh.setFormatter(fmt)
        sh.setFormatter(fmt)
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(fh)
        self.logger.addHandler(sh)

    def _prepare_browser( self ):
        self.br = mechanize.Browser()
        self.br.set_handle_equiv(True)
        self.br.set_handle_redirect(True)
        self.br.set_handle_referer(True)
        self.br.set_handle_robots(False)
        self.br.addheaders = self.HEADERS

    def download_api_files( self ):

        # Scarico file Players
        resp = self.br.open(self.PAGES['players'], timeout=10)
        file("players.xml", 'w').write(resp.get_data().decode())

        # Scarico galassia
        resp = self.br.open(self.PAGES['galaxy'], timeout=10)
        file("galaxy.xml", 'w').write(resp.get_data().decode())

        # Scarico classifica Generale
        resp = self.br.open(self.PAGES['general'], timeout=10)
        file("general.xml", 'w').write(resp.get_data().decode())

        # Scarico classifica militare
        resp = self.br.open(self.PAGES['military'], timeout=10)
        file("military.xml", 'w').write(resp.get_data().decode())

    def find_inactive_nearby(self, from_planet, radius=100, min_ponts=20000 ):
        self.logger.info("Searching inactives near %s in radius %s" % (from_planet, radius))

        scores = etree.parse('general.xml').getroot()
        military_scores = etree.parse('military.xml').getroot()
        players = etree.parse('players.xml').getroot()
        galaxy = etree.parse('galaxy.xml').getroot()

        inactives=[]

        for player in players.findall('player'):
            status = player.get('status')
            if status == 'i' or status == 'I':
                p = Player(idx=player.get('id'), name=player.get('name'))
                p.score = self.get_score(player=p, scores=scores)
                p.military_score = self.get_score(player=p, scores=military_scores)

                if int(p.score) > min_ponts:
                    inactives.append(p)
                    for planet in galaxy.findall('planet[@player=\''+p.idx+'\']'):
                        pl = Planet(id=planet.get('id'),
                                    name=planet.get('name'),
                                    coords=planet.get('coords'),
                                    url=None)
                        if from_planet.is_in_range(coords=pl.coords, radius=radius):
                           self.logger.info(pl.coords)
                           p.planets.append(pl)

        return inactives

    @staticmethod
    def get_score(player, scores):
        score = scores.find('player[@id=\''+player.idx+'\']')
        return score.get('score')

if __name__ == "__main__":
    # Carico inattivi
    planet = Planet(id="1", name="Prova", coords="2:1:1", url="1")
    inactive_finder = InactiveFinder()
    # inactive_finder.download_api_files();
    inattivi = inactive_finder.find_inactive_nearby(from_planet=planet, radius=200, min_ponts=20000)

