export const isEmail = (email: string): boolean => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);

export const isStrongPassword = (password: string): { valid: boolean; errors: string[] } => {
  const errors: string[] = [];
  if (password.length < 8) errors.push('At least 8 characters');
  if (!/[A-Z]/.test(password)) errors.push('At least one uppercase letter');
  if (!/[a-z]/.test(password)) errors.push('At least one lowercase letter');
  if (!/[0-9]/.test(password)) errors.push('At least one number');
  if (!/[^A-Za-z0-9]/.test(password)) errors.push('At least one special character');
  return { valid: errors.length === 0, errors };
};

export const isPhone = (phone: string): boolean => /^\+?[\d\s\-()]{7,15}$/.test(phone);

export const isURL = (url: string): boolean => {
  try { new URL(url); return true; } catch { return false; }
};

export const isRequired = (value: any): boolean => {
  if (value === null || value === undefined) return false;
  if (typeof value === 'string') return value.trim().length > 0;
  if (Array.isArray(value)) return value.length > 0;
  return true;
};

export const isMinLength = (value: string, min: number): boolean => value.length >= min;
export const isMaxLength = (value: string, max: number): boolean => value.length <= max;
export const isInRange = (value: number, min: number, max: number): boolean => value >= min && value <= max;
export const isPositive = (value: number): boolean => value > 0;
export const isInteger = (value: number): boolean => Number.isInteger(value);

export const isDateInFuture = (date: string | Date): boolean => {
  const d = typeof date === 'string' ? new Date(date) : date;
  return d > new Date();
};

export const isDateInPast = (date: string | Date): boolean => {
  const d = typeof date === 'string' ? new Date(date) : date;
  return d < new Date();
};

export interface ValidationRule {
  validator: (value: any) => boolean;
  message: string;
}

export const validate = (value: any, rules: ValidationRule[]): string[] => {
  return rules.filter(rule => !rule.validator(value)).map(rule => rule.message);
};

export const validateForm = <T extends Record<string, any>>(
  data: T,
  schema: Record<keyof T, ValidationRule[]>
): Record<keyof T, string[]> => {
  const errors = {} as Record<keyof T, string[]>;
  for (const [field, rules] of Object.entries(schema)) {
    const fieldErrors = validate(data[field as keyof T], rules as ValidationRule[]);
    if (fieldErrors.length > 0) errors[field as keyof T] = fieldErrors;
  }
  return errors;
};

export const hasErrors = (errors: Record<string, string[]>): boolean => {
  return Object.values(errors).some(e => e.length > 0);
};
