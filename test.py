def read_spio_messages(self):
    resp = self.br.open(self._get_url('messages'))
    soup = BeautifulSoup(resp)
    idMsgNew = soup.findAll('li','msg msg_new').get('data-msg-id')
    for id in idMsgNew
        self.logger.info('messaggio con id: ' +str(id))