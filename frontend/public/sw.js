self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (event) => event.waitUntil(clients.claim()));

let pageVisible = false;

self.addEventListener('message', (event) => {
  if (event.data === 'page-visible') pageVisible = true;
  if (event.data === 'page-hidden') pageVisible = false;
});

self.addEventListener('push', (event) => {
  let data = { title: 'Connie', body: '有新消息', url: '/', tag: 'remoire' };
  try {
    if (event.data) data = { ...data, ...event.data.json() };
  } catch (e) {}

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((list) => {
      const hasFocused = list.some((c) => c.focused || c.visibilityState === 'visible');
      if (hasFocused || pageVisible) return;
      return self.registration.showNotification(data.title, {
        body: data.body,
        icon: '/icon-192.png',
        badge: '/icon-192.png',
        tag: data.tag,
        renotify: true,
        data: { url: data.url },
      });
    })
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = event.notification.data?.url || '/';
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((list) => {
      for (const client of list) {
        if (client.url.includes(self.location.origin) && 'focus' in client) {
          return client.focus();
        }
      }
      return clients.openWindow(url);
    })
  );
});
