const authUrl = window.AUTH_SERVICE_URL || 'http://localhost:8101';
const tenantUrl = window.TENANT_SERVICE_URL || 'http://localhost:8102';
const aiUrl = window.AI_SERVICE_URL || 'http://localhost:8105';
const output = document.getElementById('output');
let accessToken = null;

const show = (data) => {
  output.textContent = JSON.stringify(data, null, 2);
};

function authHeaders() {
  if (!accessToken) throw new Error('Create a session first.');
  return { Authorization: 'Bearer ' + accessToken };
}

document.getElementById('createSession').addEventListener('click', async () => {
  const role = document.getElementById('role').value;
  const scopesByRole = {
    Resident: ['tenant:read', 'ai:assist'],
    Partner: ['tenant:read', 'ai:assist'],
    Municipality: ['tenant:read', 'ai:assist'],
  };
  const response = await fetch(`${authUrl}/api/v2/auth/session`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      provider: 'passkey',
      subject: document.getElementById('subject').value,
      tenant_id: document.getElementById('tenantId').value,
      role,
      scopes: scopesByRole[role] || ['tenant:read'],
    }),
  });
  const body = await response.json();
  if (!response.ok) return show(body);
  accessToken = body.access_token;
  show(body);
});

document.getElementById('loadCases').addEventListener('click', async () => {
  const response = await fetch(`${tenantUrl}/api/v2/cases`, { headers: authHeaders() });
  show(await response.json());
});

document.getElementById('askAi').addEventListener('click', async () => {
  const response = await fetch(`${aiUrl}/api/v2/ai/assist`, {
    method: 'POST',
    headers: { 'content-type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ case_id: 'demo-case', prompt: 'How should I prepare my next filing?' }),
  });
  show(await response.json());
});
