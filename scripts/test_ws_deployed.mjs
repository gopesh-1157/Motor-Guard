async function testDeployedWs() {
  const res = await fetch('https://motor-guard.onrender.com/api/v1/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'admin', password: 'adminpassword123' }),
  });
  const data = await res.json();
  const token = data.access_token;
  console.log('Obtained token for admin.');

  const wsUrl = `wss://motor-guard.onrender.com/ws/telemetry`;
  console.log(`Connecting to WebSocket: ${wsUrl} with subprotocol ['access_token', token]...`);

  const ws = new WebSocket(wsUrl, ['access_token', token]);

  const timer = setTimeout(() => {
    console.error('WebSocket connection TIMEOUT (10s)');
    ws.close();
    process.exit(1);
  }, 10000);

  ws.onopen = () => {
    clearTimeout(timer);
    console.log('>>> WebSocket CONNECTED SUCCESSFULLY to Render backend! <<<');
    setTimeout(() => {
      console.log('Closing WebSocket cleanly.');
      ws.close();
      process.exit(0);
    }, 2000);
  };

  ws.onmessage = (event) => {
    console.log('WS message received:', event.data);
  };

  ws.onerror = (err) => {
    clearTimeout(timer);
    console.error('WebSocket ERROR event fired');
    process.exit(1);
  };

  ws.onclose = (event) => {
    console.log(`WebSocket closed with code ${event.code}, reason: ${event.reason}`);
  };
}

testDeployedWs();
