const API = {
  auth: window.AUTH_SERVICE_URL || 'http://localhost:8101',
  tenant: window.TENANT_SERVICE_URL || 'http://localhost:8102',
  documents: window.DOCUMENTS_SERVICE_URL || 'http://localhost:8103',
  ai: window.AI_SERVICE_URL || 'http://localhost:8105',
};

const output = document.getElementById('output');
let accessToken = null;

const show = (value) => {
  output.textContent = JSON.stringify(value, null, 2);
};

function parseScopes(value) {
  return (value || '')
    .split(',')
    .map((scope) => scope.trim())
    .filter(Boolean);
}

function authHeaders() {
  if (!accessToken) throw new Error('Create a session first.');
  return { Authorization: 'Bearer ' + accessToken };
}

async function post(url, body, headers = {}) {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'content-type': 'application/json', ...headers },
    body: JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(JSON.stringify(data));
  return data;
}

document.getElementById('createSession').addEventListener('click', async () => {
  try {
    const data = await post(`${API.auth}/api/v2/auth/session`, {
      provider: document.getElementById('provider').value,
      subject: document.getElementById('subject').value,
      email: document.getElementById('email').value,
      tenant_id: document.getElementById('tenantId').value,
      role: document.getElementById('role').value,
      scopes: parseScopes(document.getElementById('scopes').value),
    });
    accessToken = data.access_token;
    show(data);
  } catch (error) {
    show({ error: String(error) });
  }
});

document.getElementById('createCase').addEventListener('click', async () => {
  try {
    const data = await post(`${API.tenant}/api/v2/cases`, {
      tenant_id: document.getElementById('tenantId').value,
      title: document.getElementById('caseTitle').value,
    }, authHeaders());
    document.getElementById('docCaseId').value = data.id;
    document.getElementById('aiCaseId').value = data.id;
    show(data);
  } catch (error) {
    show({ error: String(error) });
  }
});

document.getElementById('generateDoc').addEventListener('click', async () => {
  try {
    const data = await post(`${API.documents}/api/v2/documents/generate`, {
      case_id: document.getElementById('docCaseId').value,
      template_id: document.getElementById('templateId').value,
      output_format: document.getElementById('docFormat').value,
      fields: { sample: true },
    }, authHeaders());
    show(data);
  } catch (error) {
    show({ error: String(error) });
  }
});

document.getElementById('askAi').addEventListener('click', async () => {
  try {
    const data = await post(`${API.ai}/api/v2/ai/assist`, {
      case_id: document.getElementById('aiCaseId').value,
      prompt: document.getElementById('aiPrompt').value,
    }, authHeaders());
    show(data);
  } catch (error) {
    show({ error: String(error) });
  }
});
