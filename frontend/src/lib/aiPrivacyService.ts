const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export interface AIFieldPrivacyItem {
  field_name: string;
  include_in_ai: boolean;
  updated_at?: string;
  updated_by_user_id?: string;
}

export type QuestionnaireType = 'sale_ready' | 'value_builder';

function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem('auth_token');
  return {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
  };
}

export async function getFieldConfigs(questionnaireType: QuestionnaireType): Promise<AIFieldPrivacyItem[]> {
  const res = await fetch(`${API_BASE_URL}/api/ai-field-privacy/${questionnaireType}`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error(`Failed to load AI privacy config: ${res.status}`);
  const data = await res.json();
  return data.fields as AIFieldPrivacyItem[];
}

export async function updateFieldConfigs(
  questionnaireType: QuestionnaireType,
  fields: AIFieldPrivacyItem[],
): Promise<AIFieldPrivacyItem[]> {
  const res = await fetch(`${API_BASE_URL}/api/ai-field-privacy/${questionnaireType}`, {
    method: 'PUT',
    headers: getAuthHeaders(),
    body: JSON.stringify({ fields }),
  });
  if (!res.ok) throw new Error(`Failed to save AI privacy config: ${res.status}`);
  const data = await res.json();
  return data.fields as AIFieldPrivacyItem[];
}
