import axios from 'axios';
import { SystemColonizationData, CurrentSystem } from '../types/colonization';
import { AppSettings } from '../types/settings';

const API_BASE_URL = '/api';

export const api = {
  // Get all systems with construction
  async getSystems(): Promise<string[]> {
    const response = await axios.get<{ systems: string[] }>(`${API_BASE_URL}/systems`);
    return response.data.systems;
  },

  // Search systems by name
  async searchSystems(query: string): Promise<string[]> {
    const response = await axios.get<{ systems: string[] }>(`${API_BASE_URL}/systems/search`, {
      params: { q: query },
      paramsSerializer: params => {
        return Object.entries(params)
          .map(([key, value]) => `${key}=${encodeURIComponent(value)}`)
          .join('&');
      }
    });
    return response.data.systems;
  },

  // Get current player system
  async getCurrentSystem(): Promise<CurrentSystem> {
    const response = await axios.get<CurrentSystem>(`${API_BASE_URL}/journal/status`);
    return response.data;
  },

  // Get system colonization data
  async getSystemData(systemName: string): Promise<SystemColonizationData> {
    const response = await axios.get<SystemColonizationData>(`${API_BASE_URL}/system`, {
      params: { name: systemName },
      paramsSerializer: params => {
        return Object.entries(params)
          .map(([key, value]) => `${key}=${encodeURIComponent(value)}`)
          .join('&');
      }
    });
    return response.data;
  },

  // Health check
  async healthCheck(): Promise<{ status: string; version: string }> {
    const response = await axios.get(`${API_BASE_URL}/health`);
    return response.data;
  },

  // Get app settings
  async getAppSettings(): Promise<AppSettings> {
    const response = await axios.get<AppSettings>(`${API_BASE_URL}/settings`);
    return response.data;
  },

  // Update app settings
  async updateAppSettings(settings: AppSettings): Promise<AppSettings> {
    const response = await axios.post<AppSettings>(`${API_BASE_URL}/settings`, settings);
    return response.data;
  },
};