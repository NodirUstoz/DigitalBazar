import React, { useState, useEffect } from 'react';

interface Column<T> {
  key: keyof T;
  label: string;
  render?: (value: any, item: T) => React.ReactNode;
  sortable?: boolean;
  width?: string;
}

interface GenericListProps<T> {
  title: string;
  apiUrl: string;
  columns: Column<T>[];
  onAdd?: () => void;
  onEdit?: (item: T) => void;
  onDelete?: (item: T) => void;
  searchPlaceholder?: string;
}

function GenericList<T extends { id: number | string }>({
  title, apiUrl, columns, onAdd, onEdit, onDelete, searchPlaceholder = 'Search...',
}: GenericListProps<T>) {
  const [items, setItems] = useState<T[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [sortKey, setSortKey] = useState<keyof T | null>(null);
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
  const pageSize = 20;

  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true);
      try {
        const tokens = JSON.parse(localStorage.getItem('auth_tokens') || 'null');
        const params = new URLSearchParams({
          page: String(currentPage),
          page_size: String(pageSize),
          ...(searchQuery ? { search: searchQuery } : {}),
          ...(sortKey ? { ordering: `${sortOrder === 'desc' ? '-' : ''}${String(sortKey)}` } : {}),
        });
        const res = await fetch(`${apiUrl}?${params}`, {
          headers: tokens?.access ? { Authorization: `Bearer ${tokens.access}` } : {},
        });
        if (res.ok) {
          const data = await res.json();
          setItems(data.results || data.data || []);
          setTotalCount(data.count || data.total || 0);
          setTotalPages(Math.ceil((data.count || data.total || 0) / pageSize));
        }
      } catch (err) {
        console.error('Failed to fetch:', err);
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, [apiUrl, currentPage, searchQuery, sortKey, sortOrder]);

  const handleSort = (key: keyof T) => {
    if (sortKey === key) {
      setSortOrder(prev => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortOrder('asc');
    }
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{title}</h1>
          <p className="text-sm text-gray-500 mt-1">{totalCount} total items</p>
        </div>
        {onAdd && (
          <button onClick={onAdd} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium text-sm">
            + Add New
          </button>
        )}
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200">
        <div className="p-4 border-b border-gray-200">
          <input type="text" placeholder={searchPlaceholder} value={searchQuery}
            onChange={e => { setSearchQuery(e.target.value); setCurrentPage(1); }}
            className="w-full max-w-md px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent" />
        </div>

        {isLoading ? (
          <div className="p-12 text-center text-gray-500">Loading...</div>
        ) : items.length === 0 ? (
          <div className="p-12 text-center text-gray-500">No items found</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="bg-gray-50">
                  {columns.map(col => (
                    <th key={String(col.key)} className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                      style={{ width: col.width }}>
                      {col.sortable ? (
                        <button onClick={() => handleSort(col.key)} className="flex items-center space-x-1 hover:text-gray-700">
                          <span>{col.label}</span>
                          {sortKey === col.key && <span>{sortOrder === 'asc' ? ' ^' : ' v'}</span>}
                        </button>
                      ) : col.label}
                    </th>
                  ))}
                  {(onEdit || onDelete) && <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Actions</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {items.map(item => (
                  <tr key={String(item.id)} className="hover:bg-gray-50">
                    {columns.map(col => (
                      <td key={String(col.key)} className="px-6 py-4 text-sm text-gray-900">
                        {col.render ? col.render(item[col.key], item) : String(item[col.key] ?? '')}
                      </td>
                    ))}
                    {(onEdit || onDelete) && (
                      <td className="px-6 py-4 text-right space-x-2">
                        {onEdit && <button onClick={() => onEdit(item)} className="text-blue-600 hover:text-blue-800 text-sm font-medium">Edit</button>}
                        {onDelete && <button onClick={() => onDelete(item)} className="text-red-600 hover:text-red-800 text-sm font-medium">Delete</button>}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {totalPages > 1 && (
          <div className="px-6 py-3 border-t border-gray-200 flex items-center justify-between">
            <span className="text-sm text-gray-500">Page {currentPage} of {totalPages}</span>
            <div className="flex space-x-2">
              <button onClick={() => setCurrentPage(p => Math.max(1, p - 1))} disabled={currentPage === 1}
                className="px-3 py-1 border border-gray-300 rounded text-sm disabled:opacity-50 hover:bg-gray-50">Previous</button>
              <button onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))} disabled={currentPage === totalPages}
                className="px-3 py-1 border border-gray-300 rounded text-sm disabled:opacity-50 hover:bg-gray-50">Next</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default GenericList;
