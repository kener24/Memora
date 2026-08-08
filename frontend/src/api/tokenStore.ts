const REFRESH_TOKEN_KEY = "memora_refresh_token";

let accessToken: string | null = null;

export const tokenStore = {
  getAccess(): string | null {
    return accessToken;
  },
  setAccess(token: string | null): void {
    accessToken = token;
  },
  getRefresh(): string | null {
    return sessionStorage.getItem(REFRESH_TOKEN_KEY);
  },
  setRefresh(token: string): void {
    sessionStorage.setItem(REFRESH_TOKEN_KEY, token);
  },
  clear(): void {
    accessToken = null;
    sessionStorage.removeItem(REFRESH_TOKEN_KEY);
  },
};

