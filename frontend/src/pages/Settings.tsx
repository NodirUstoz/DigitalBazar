import React, { useState, useEffect } from 'react';

interface ProfileData {
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  avatar?: string;
  timezone: string;
  language: string;
}

interface PasswordData {
  current_password: string;
  new_password: string;
  confirm_password: string;
}

interface NotificationSettings {
  email_notifications: boolean;
  push_notifications: boolean;
  weekly_digest: boolean;
  marketing_emails: boolean;
}

const Settings: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'profile' | 'password' | 'notifications' | 'appearance'>('profile');
  const [profile, setProfile] = useState<ProfileData>({
    first_name: '', last_name: '', email: '', phone: '', timezone: 'UTC', language: 'en',
  });
  const [passwords, setPasswords] = useState<PasswordData>({
    current_password: '', new_password: '', confirm_password: '',
  });
  const [notifications, setNotifications] = useState<NotificationSettings>({
    email_notifications: true, push_notifications: true, weekly_digest: false, marketing_emails: false,
  });
  const [theme, setTheme] = useState<'light' | 'dark' | 'system'>('light');
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const tokens = JSON.parse(localStorage.getItem('auth_tokens') || 'null');
        const res = await fetch('/api/v1/auth/me/', {
          headers: tokens?.access ? { Authorization: `Bearer ${tokens.access}` } : {},
        });
        if (res.ok) {
          const data = await res.json();
          setProfile({
            first_name: data.first_name || '', last_name: data.last_name || '',
            email: data.email || '', phone: data.phone || '',
            timezone: data.timezone || 'UTC', language: data.language || 'en',
          });
        }
      } catch (err) {
        console.error('Failed to fetch profile:', err);
      }
    };
    fetchProfile();
  }, []);

  const handleSaveProfile = async () => {
    setIsSaving(true);
    setMessage(null);
    try {
      const tokens = JSON.parse(localStorage.getItem('auth_tokens') || 'null');
      const res = await fetch('/api/v1/auth/me/', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', ...(tokens?.access ? { Authorization: `Bearer ${tokens.access}` } : {}) },
        body: JSON.stringify(profile),
      });
      if (!res.ok) throw new Error('Failed to update profile');
      setMessage({ type: 'success', text: 'Profile updated successfully' });
    } catch {
      setMessage({ type: 'error', text: 'Failed to update profile' });
    } finally {
      setIsSaving(false);
    }
  };

  const handleChangePassword = async () => {
    if (passwords.new_password !== passwords.confirm_password) {
      setMessage({ type: 'error', text: 'Passwords do not match' });
      return;
    }
    setIsSaving(true);
    setMessage(null);
    try {
      const tokens = JSON.parse(localStorage.getItem('auth_tokens') || 'null');
      const res = await fetch('/api/v1/auth/change-password/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(tokens?.access ? { Authorization: `Bearer ${tokens.access}` } : {}) },
        body: JSON.stringify({ old_password: passwords.current_password, new_password: passwords.new_password }),
      });
      if (!res.ok) throw new Error('Failed to change password');
      setPasswords({ current_password: '', new_password: '', confirm_password: '' });
      setMessage({ type: 'success', text: 'Password changed successfully' });
    } catch {
      setMessage({ type: 'error', text: 'Failed to change password' });
    } finally {
      setIsSaving(false);
    }
  };

  const tabs = [
    { id: 'profile' as const, label: 'Profile' },
    { id: 'password' as const, label: 'Password' },
    { id: 'notifications' as const, label: 'Notifications' },
    { id: 'appearance' as const, label: 'Appearance' },
  ];

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Settings</h1>

      {message && (
        <div className={`mb-4 px-4 py-3 rounded-lg text-sm ${message.type === 'success' ? 'bg-green-50 text-green-800 border border-green-200' : 'bg-red-50 text-red-800 border border-red-200'}`}>
          {message.text}
        </div>
      )}

      <div className="flex space-x-1 bg-gray-100 rounded-lg p-1 mb-6">
        {tabs.map(tab => (
          <button key={tab.id} onClick={() => setActiveTab(tab.id)}
            className={`flex-1 px-4 py-2 text-sm font-medium rounded-md transition-colors ${activeTab === tab.id ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-600 hover:text-gray-900'}`}>
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'profile' && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-6">
          <h2 className="text-lg font-semibold">Profile Information</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">First Name</label>
              <input value={profile.first_name} onChange={e => setProfile(p => ({ ...p, first_name: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Last Name</label>
              <input value={profile.last_name} onChange={e => setProfile(p => ({ ...p, last_name: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
              <input type="email" value={profile.email} onChange={e => setProfile(p => ({ ...p, email: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Phone</label>
              <input value={profile.phone} onChange={e => setProfile(p => ({ ...p, phone: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent" />
            </div>
          </div>
          <button onClick={handleSaveProfile} disabled={isSaving}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium disabled:opacity-50">
            {isSaving ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      )}

      {activeTab === 'password' && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-6">
          <h2 className="text-lg font-semibold">Change Password</h2>
          <div className="max-w-md space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Current Password</label>
              <input type="password" value={passwords.current_password}
                onChange={e => setPasswords(p => ({ ...p, current_password: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">New Password</label>
              <input type="password" value={passwords.new_password}
                onChange={e => setPasswords(p => ({ ...p, new_password: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Confirm New Password</label>
              <input type="password" value={passwords.confirm_password}
                onChange={e => setPasswords(p => ({ ...p, confirm_password: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500" />
            </div>
          </div>
          <button onClick={handleChangePassword} disabled={isSaving}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium disabled:opacity-50">
            {isSaving ? 'Changing...' : 'Change Password'}
          </button>
        </div>
      )}

      {activeTab === 'notifications' && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-4">
          <h2 className="text-lg font-semibold">Notification Preferences</h2>
          {Object.entries(notifications).map(([key, value]) => (
            <label key={key} className="flex items-center justify-between py-3 border-b border-gray-100 last:border-0">
              <span className="text-sm text-gray-700">{key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</span>
              <button onClick={() => setNotifications(n => ({ ...n, [key]: !value }))}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${value ? 'bg-blue-600' : 'bg-gray-200'}`}>
                <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${value ? 'translate-x-6' : 'translate-x-1'}`} />
              </button>
            </label>
          ))}
        </div>
      )}

      {activeTab === 'appearance' && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-4">
          <h2 className="text-lg font-semibold">Appearance</h2>
          <div className="grid grid-cols-3 gap-4">
            {(['light', 'dark', 'system'] as const).map(t => (
              <button key={t} onClick={() => setTheme(t)}
                className={`p-4 rounded-lg border-2 text-center transition-colors ${theme === t ? 'border-blue-600 bg-blue-50' : 'border-gray-200 hover:border-gray-300'}`}>
                <span className="block text-2xl mb-2">{t === 'light' ? 'Sun' : t === 'dark' ? 'Moon' : 'Auto'}</span>
                <span className="text-sm font-medium">{t.charAt(0).toUpperCase() + t.slice(1)}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default Settings;
