const tenantUrl = window.TENANT_SERVICE_URL || 'http://localhost:8102';
const aiUrl = window.AI_SERVICE_URL || 'http://localhost:8105';
const output = document.getElementById('output');

const show = (data) => {
  output.textContent = JSON.stringify(data, null, 2);
};

document.getElementById('loadCases').addEventListener('click', async () => {
  const response = await fetch(`${tenantUrl}/api/v2/cases`);
  show(await response.json());
});

document.getElementById('askAi').addEventListener('click', async () => {
  const response = await fetch(`${aiUrl}/api/v2/ai/assist`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ case_id: 'demo-case', prompt: 'How should I prepare my next filing?' }),
  });
  show(await response.json());
});
