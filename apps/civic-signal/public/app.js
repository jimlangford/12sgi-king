const authUrl = window.AUTH_SERVICE_URL || 'http://localhost:8101';
const tenantUrl = window.TENANT_SERVICE_URL || 'http://localhost:8102';
const healthUrl = window.HEALTH_SERVICE_URL || 'http://localhost:8106';
const output = document.getElementById('output');
let accessToken = null;

function authHeaders() {
  if (!accessToken) throw new Error('Create a session first.');
  return { Authorization: 'Bearer ' + accessToken };
}

document.getElementById('createSession').addEventListener('click', async () => {
  const response = await fetch(`${authUrl}/api/v2/auth/session`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      provider: 'passkey',
      subject: document.getElementById('subject').value,
      tenant_id: document.getElementById('tenantId').value,
      role: 'Partner',
      scopes: ['tenant:read'],
    }),
  });
  const body = await response.json();
  if (!response.ok) {
    output.textContent = JSON.stringify(body, null, 2);
    return;
  }
  accessToken = body.access_token;
  output.textContent = JSON.stringify(body, null, 2);
});

document.getElementById('metrics').addEventListener('click', async () => {
  const [casesRes, healthRes] = await Promise.all([
    fetch(`${tenantUrl}/api/v2/cases`, { headers: authHeaders() }),
    fetch(`${healthUrl}/api/v1/health`),
  ]);
  const [cases, health] = await Promise.all([casesRes.json(), healthRes.json()]);
  output.textContent = JSON.stringify(
    {
      total_cases: cases.cases?.length || 0,
      backend_status: health.status,
      checked_at: new Date().toISOString(),
    },
    null,
    2,
  );
});
