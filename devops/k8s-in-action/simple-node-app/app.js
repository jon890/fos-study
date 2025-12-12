const express = require('express');

const app = express();

const PORT = process.env.PORT || 3000;
const HOSTNAME = process.env.HOSTNAME || 'unknown';

app.get('/', (req, res) => {
  res
    .status(200)
    .type('text/plain')
    .send(`hello from simple-node-app\nhostname=${HOSTNAME}\n`);
});

app.get('/healthz', (req, res) => {
  res.status(200).send('ok');
});

app.listen(PORT, () => {
  // eslint-disable-next-line no-console
  console.log(`listening on :${PORT}`);
});
