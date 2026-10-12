// History stores authenticated image URLs; the send API expects image bytes.
export async function resolveChatImage(image, apiBase, fetchImage) {
  if (!image || image.startsWith('data:')) return image;
  const prefix = `${apiBase}/chat/image/`;
  if (!image.startsWith(prefix) || !/^[a-f0-9-]{36}$/.test(image.slice(prefix.length))) {
    throw new Error('这张图片无法重新读取，请重新选择图片后发送');
  }
  const response = await fetchImage(`/chat/image/${image.slice(prefix.length)}`);
  if (!response.ok) throw new Error('原图读取失败，请稍后重试');
  const blob = await response.blob();
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error('原图读取失败，请稍后重试'));
    reader.readAsDataURL(blob);
  });
}
