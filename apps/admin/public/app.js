const endpoints = {
  auth: window.AUTH_SERVICE_URL || 'http://localhost:8101',
  tenant: window.TENANT_SERVICE_URL || 'http://localhost:8102',
  documents: window.DOCUMENTS_SERVICE_URL || 'http://localhost:8103',
  storage: window.STORAGE_SERVICE_URL || 'http://localhost:8104',
  ai: window.AI_SERVICE_URL || 'http://localhost:8105',
  health: window.HEALTH_SERVICE_URL || 'http://localhost:8000',
};

const output = document.getElementById('output');

async function getJson(url) {
  const response = await fetch(url);
  return response.json();
}

document.getElementById('health').addEventListener('click', async () => {
  const snapshot = {
    auth: await getJson(`${endpoints.auth}/api/v2/health`),
    tenant: await getJson(`${endpoints.tenant}/api/v2/health`),
    documents: await getJson(`${endpoints.documents}/api/v2/health`),
    storage: await getJson(`${endpoints.storage}/api/v2/health`),
    ai: await getJson(`${endpoints.ai}/api/v2/health`),
    gateway: await getJson(`${endpoints.health}/api/v1/health`),
  };
  output.textContent = JSON.stringify(snapshot, null, 2);
});
