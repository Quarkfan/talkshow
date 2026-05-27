// auth.js — login state management
async function checkAuth() {
  try {
    const res = await fetch('/api/me', { credentials: 'same-origin' });
    if (res.ok) return await res.json();
  } catch (e) {}
  return null;
}

async function logout() {
  await fetch('/api/logout', { method: 'POST', credentials: 'same-origin' });
  window.location.href = '/login';
}

function requireAuth(redirectTo = '/login') {
  checkAuth().then(user => {
    if (!user) window.location.href = redirectTo;
  });
}
