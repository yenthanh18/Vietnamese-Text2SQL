const API_URL = 'https://pal-westminster-allocated-informational.trycloudflare.com';

export async function request(path, options = {}) {
  const { timeoutMs = 20000, ...fetchOptions } = options;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${API_URL}${path}`, { ...fetchOptions, signal: controller.signal });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(typeof data.detail === 'string'
        ? data.detail : 'Yêu cầu không hợp lệ. Vui lòng kiểm tra và thử lại.');
    }
    return data;
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('Yêu cầu quá thời gian chờ. Vui lòng thử lại.');
    if (error instanceof TypeError) throw new Error('Không thể gọi backend. Kiểm tra FastAPI tại cổng 8000.');
    throw error;
  } finally {
    clearTimeout(timer);
  }
}
