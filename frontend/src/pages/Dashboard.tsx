import React, { useState, useEffect } from 'react';

interface StatsCard {
  title: string;
  value: string | number;
  change: number;
  changeLabel: string;
  icon: string;
}

interface RecentActivity {
  id: number;
  action: string;
  description: string;
  user: string;
  timestamp: string;
  type: 'create' | 'update' | 'delete' | 'info';
}

const Dashboard: React.FC = () => {
  const [stats, setStats] = useState<StatsCard[]>([]);
  const [activities, setActivities] = useState<RecentActivity[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [period, setPeriod] = useState<'day' | 'week' | 'month'>('week');

  useEffect(() => {
    const fetchDashboardData = async () => {
      setIsLoading(true);
      try {
        const tokens = JSON.parse(localStorage.getItem('auth_tokens') || 'null');
        const headers: Record<string, string> = {};
        if (tokens?.access) headers.Authorization = `Bearer ${tokens.access}`;

        const [statsRes, activityRes] = await Promise.all([
          fetch(`/api/v1/dashboard/stats/?period=${period}`, { headers }),
          fetch('/api/v1/dashboard/activity/', { headers }),
        ]);

        if (statsRes.ok) {
          const data = await statsRes.json();
          setStats(data.stats || [
            { title: 'Total Users', value: data.total_users || 0, change: 12.5, changeLabel: 'vs last period', icon: 'users' },
            { title: 'Revenue', value: `$${(data.revenue || 0).toLocaleString()}`, change: 8.2, changeLabel: 'vs last period', icon: 'dollar' },
            { title: 'Active Projects', value: data.active_projects || 0, change: -2.1, changeLabel: 'vs last period', icon: 'folder' },
            { title: 'Completion Rate', value: `${data.completion_rate || 0}%`, change: 5.3, changeLabel: 'vs last period', icon: 'check' },
          ]);
        }

        if (activityRes.ok) {
          const data = await activityRes.json();
          setActivities(data.results || data.activities || []);
        }
      } catch (error) {
        console.error('Failed to fetch dashboard data:', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchDashboardData();
  }, [period]);

  const getChangeColor = (change: number) => change >= 0 ? 'text-green-600' : 'text-red-600';
  const getChangeArrow = (change: number) => change >= 0 ? 'arrow-up' : 'arrow-down';

  const getActivityTypeStyles = (type: string) => {
    switch (type) {
      case 'create': return 'bg-green-100 text-green-800';
      case 'update': return 'bg-blue-100 text-blue-800';
      case 'delete': return 'bg-red-100 text-red-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  if (isLoading) {
    return (
      <div className="p-6 space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 animate-pulse">
              <div className="h-4 bg-gray-200 rounded w-1/2 mb-4" />
              <div className="h-8 bg-gray-200 rounded w-3/4 mb-2" />
              <div className="h-3 bg-gray-200 rounded w-1/3" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-sm text-gray-500 mt-1">Overview of your platform metrics</p>
        </div>
        <div className="flex items-center space-x-2 bg-gray-100 rounded-lg p-1">
          {(['day', 'week', 'month'] as const).map(p => (
            <button key={p} onClick={() => setPeriod(p)}
              className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                period === p ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-600 hover:text-gray-900'
              }`}>
              {p.charAt(0).toUpperCase() + p.slice(1)}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {stats.map((stat, index) => (
          <div key={index} className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 hover:shadow-md transition-shadow">
            <div className="flex items-center justify-between mb-4">
              <span className="text-sm font-medium text-gray-500">{stat.title}</span>
              <span className="w-10 h-10 bg-blue-50 rounded-lg flex items-center justify-center text-blue-600">
                {stat.icon === 'users' && 'U'}
                {stat.icon === 'dollar' && '$'}
                {stat.icon === 'folder' && 'F'}
                {stat.icon === 'check' && 'C'}
              </span>
            </div>
            <div className="text-2xl font-bold text-gray-900 mb-1">{stat.value}</div>
            <div className="flex items-center text-sm">
              <span className={getChangeColor(stat.change)}>
                {stat.change >= 0 ? '+' : ''}{stat.change}%
              </span>
              <span className="text-gray-400 ml-1">{stat.changeLabel}</span>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Analytics Overview</h2>
          <div className="h-64 flex items-center justify-center text-gray-400 border border-dashed border-gray-200 rounded-lg">
            Chart Component - Integrate with Recharts or Chart.js
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Recent Activity</h2>
          <div className="space-y-4 max-h-64 overflow-y-auto">
            {activities.length > 0 ? activities.map(activity => (
              <div key={activity.id} className="flex items-start space-x-3">
                <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium mt-0.5 ${getActivityTypeStyles(activity.type)}`}>
                  {activity.type}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-gray-900">{activity.action}</p>
                  <p className="text-xs text-gray-500">{activity.user} - {activity.timestamp}</p>
                </div>
              </div>
            )) : (
              <p className="text-sm text-gray-500 text-center py-8">No recent activity</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
