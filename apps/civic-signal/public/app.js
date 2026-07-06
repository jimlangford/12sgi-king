const tenantUrl = window.TENANT_SERVICE_URL || 'http://localhost:8102';
const healthUrl = window.HEALTH_SERVICE_URL || 'http://localhost:8000';
const output = document.getElementById('output');

document.getElementById('metrics').addEventListener('click', async () => {
  const [casesRes, healthRes] = await Promise.all([
    fetch(`${tenantUrl}/api/v2/cases`),
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
