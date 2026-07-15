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

function authHeaders(required = true) {
  if (!accessToken) {
    if (required) throw new Error('Create auth session first');
    return {};
  }
  return { Authorization: `Bearer ${accessToken}` };
}

async function post(url, body, extraHeaders = {}) {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'content-type': 'application/json', ...extraHeaders },
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
    });
    accessToken = data.access_token || null;
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
    document.getElementById('renderCaseId').value = data.id;
    document.getElementById('edgeCaseId').value = data.id;
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

document.getElementById('dispatchRender').addEventListener('click', async () => {
  try {
    const assets = document.getElementById('renderAssets').value
      .split(',')
      .map((value) => value.trim())
      .filter(Boolean);
    const routeHint = document.getElementById('renderRouteHint').value || undefined;
    const data = await post(`${API.ai}/api/v2/ai/render/dispatch`, {
      case_id: document.getElementById('renderCaseId').value || undefined,
      tenant_id: document.getElementById('renderTenantId').value || undefined,
      project_id: document.getElementById('renderProjectId').value || undefined,
      prompt: document.getElementById('renderPrompt').value,
      route_hint: routeHint,
      assets,
    }, authHeaders());
    show(data);
  } catch (error) {
    show({ error: String(error) });
  }
});

document.getElementById('upsertStringEdge').addEventListener('click', async () => {
  try {
    const contextRaw = document.getElementById('edgeContext').value.trim();
    const context = contextRaw ? JSON.parse(contextRaw) : {};
    const data = await post(`${API.ai}/api/v2/ai/graph/string-edge`, {
      source: {
        kind: document.getElementById('edgeSourceKind').value,
        id: document.getElementById('edgeSourceId').value,
      },
      relation: document.getElementById('edgeRelation').value,
      target: {
        kind: document.getElementById('edgeTargetKind').value,
        id: document.getElementById('edgeTargetId').value,
      },
      weight: Number(document.getElementById('edgeWeight').value || 1),
      case_id: document.getElementById('edgeCaseId').value || undefined,
      tenant_id: document.getElementById('edgeTenantId').value || undefined,
      project_id: document.getElementById('edgeProjectId').value || undefined,
      context,
    }, authHeaders());
    show(data);
  } catch (error) {
    show({ error: String(error) });
  }
});
