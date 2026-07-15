const API_BASE = 'http://localhost:8085/api/v1';
let currentFolderId = null;
let globalMappings = [];
let nodeMap = {};
let expandedSidebarFolders = new Set();
let selectedRowIds = new Set();
let sortAscending = false;

function toggleSort() {
    sortAscending = !sortAscending;
    renderMainArea();
}

// Fetch mappings on load
async function fetchMappings() {
    try {
        const res = await fetch(`${API_BASE}/mappings`);
        globalMappings = await res.json();
        renderApp();
    } catch (e) {
        console.error("Failed to fetch mappings", e);
    }
}

function buildTree(mappings) {
    nodeMap = {};
    mappings.forEach(m => nodeMap[m.id] = { ...m, children: [] });
    
    let roots = [];
    mappings.forEach(m => {
        if (m.parent_id && nodeMap[m.parent_id]) {
            nodeMap[m.parent_id].children.push(nodeMap[m.id]);
        } else {
            roots.push(nodeMap[m.id]);
        }
    });
    
    function sortNodes(nodes) {
        nodes.sort((a,b) => {
            if (a.item_type !== b.item_type) return a.item_type === 'folder' ? -1 : 1;
            return (a.target_url || a.description).localeCompare(b.target_url || b.description);
        });
        nodes.forEach(n => sortNodes(n.children));
    }
    sortNodes(roots);
    
    return roots;
}

function renderApp() {
    const roots = buildTree(globalMappings);
    renderSidebar(roots);
    renderBreadcrumbs();
    renderMainArea();
}

function renderSidebar(roots) {
    const sidebarTree = document.getElementById('sidebarTree');
    sidebarTree.innerHTML = '';
    
    function renderSidebarItem(node, level = 0) {
        const hasChildren = node.children.some(c => c.item_type === 'folder' || c.children.length > 0);
        if (node.item_type !== 'folder' && !hasChildren) return; 
        
        const div = document.createElement('div');
        div.className = `tree-item-container`;
        
        const itemDiv = document.createElement('div');
        itemDiv.className = `tree-item ${currentFolderId === node.id ? 'active' : ''}`;
        itemDiv.style.paddingLeft = `${level * 20 + 16}px`;
        
        itemDiv.ondragover = (e) => { e.preventDefault(); itemDiv.classList.add('drag-over'); };
        itemDiv.ondragleave = (e) => { itemDiv.classList.remove('drag-over'); };
        itemDiv.ondrop = async (e) => {
            e.preventDefault(); itemDiv.classList.remove('drag-over');
            const draggedId = e.dataTransfer.getData('text/plain');
            if (draggedId && draggedId !== node.id) { await moveNode(draggedId, node.id); }
        };

        let chevron = `<span style="width: 16px; display: inline-block;"></span>`;
        if (hasChildren) {
            const isOpen = expandedSidebarFolders.has(node.id);
            chevron = `<span class="chevron-sidebar ${isOpen ? 'open' : ''}" onclick="event.stopPropagation(); toggleSidebarFolder('${node.id}')">
                <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path></svg>
            </span>`;
        }

        const icon = `<span class="tree-item-icon"><svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"></path></svg></span>`;
        
        itemDiv.innerHTML = `${chevron}${icon}${node.description || node.target_url}`;
        itemDiv.onclick = (e) => { e.stopPropagation(); openFolder(node.id); };
        
        div.appendChild(itemDiv);
        sidebarTree.appendChild(div);
        
        if (expandedSidebarFolders.has(node.id)) {
            const childrenContainer = document.createElement('div');
            childrenContainer.className = 'tree-children';
            sidebarTree.appendChild(childrenContainer); // just for DOM order
            node.children.forEach(c => renderSidebarItem(c, level + 1));
        }
    }
    
    roots.forEach(r => renderSidebarItem(r, 0));
}

window.toggleSidebarFolder = function(id) {
    if (expandedSidebarFolders.has(id)) expandedSidebarFolders.delete(id);
    else expandedSidebarFolders.add(id);
    renderApp();
}

function openFolder(id) {
    currentFolderId = id;
    selectedRowIds.clear();
    toggleBulkActionBtn();
    document.getElementById('searchInput').value = '';
    renderApp();
}

function renderBreadcrumbs() {
    const breadcrumbs = document.getElementById('breadcrumbs');
    let path = [];
    let curr = currentFolderId ? nodeMap[currentFolderId] : null;
    while(curr) {
        path.unshift(curr);
        curr = curr.parent_id ? nodeMap[curr.parent_id] : null;
    }
    
    let html = `<span class="breadcrumb-item" onclick="openFolder(null)">Home</span>`;
    path.forEach(p => {
        html += `<span class="breadcrumb-separator">/</span>
                 <span class="breadcrumb-item" onclick="openFolder('${p.id}')">${p.description || p.target_url}</span>`;
    });
    breadcrumbs.innerHTML = html;
}

function renderMainArea() {
    const tbody = document.getElementById('proxyBody');
    tbody.innerHTML = '';
    
    const query = document.getElementById('searchInput').value.trim().toLowerCase();
    
    let itemsToRender = [];
    
    // Helper to get all descendants of a folder
    function getAllDescendants(folderId) {
        let desc = [];
        if(nodeMap[folderId]) {
            nodeMap[folderId].children.forEach(c => {
                desc.push(c);
                if (c.item_type === 'folder') {
                    desc = desc.concat(getAllDescendants(c.id));
                }
            });
        }
        return desc;
    }

    if (query) {
        itemsToRender = globalMappings.filter(m => 
            (m.description && m.description.toLowerCase().includes(query)) || 
            (m.target_url && m.target_url.toLowerCase().includes(query)) ||
            (m.local_port && m.local_port.toString().includes(query))
        );
    } else {
        if (currentFolderId === null) {
            itemsToRender = globalMappings; // All items flat
        } else {
            itemsToRender = getAllDescendants(currentFolderId);
        }
    }
    
    // Sort by created_at implicitly (or just leave as they are in globalMappings since they are ordered by created_at DESC from DB)
    // Filter out folders from the main view? The user said "hiển thị toàn bộ url" (show all urls), usually in flat view we don't show the folders themselves if we just want URLs, but let's just keep folders in the list in case they want to act on them.
    // Let's filter out folders to make it a pure URL list, as "hiển thị toàn bộ url" means just the items. But wait, if they can't see folders in the main area, they can't delete them from the main area. Let's keep them but sort them to top.
    
    if (itemsToRender.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-secondary)">No items found.</td></tr>`;
    }

    if (sortAscending) {
        itemsToRender.reverse();
    }

    itemsToRender.forEach((node, index) => {
        const tr = document.createElement('tr');
        if (selectedRowIds.has(node.id)) {
            tr.classList.add('selected');
        }
        
        tr.onclick = (e) => {
            // Ignore if clicked on a button, link, or switch
            if (e.target.closest('button') || e.target.closest('a') || e.target.closest('.switch') || e.target.closest('.target-url')) {
                return;
            }
            if (e.ctrlKey || e.metaKey) {
                if (selectedRowIds.has(node.id)) selectedRowIds.delete(node.id);
                else selectedRowIds.add(node.id);
            } else {
                if (selectedRowIds.has(node.id) && selectedRowIds.size === 1) {
                    selectedRowIds.clear();
                } else {
                    selectedRowIds.clear();
                    selectedRowIds.add(node.id);
                }
            }
            renderMainArea();
            toggleBulkActionBtn();
        };

        tr.draggable = true;
        tr.ondragstart = (e) => {
            e.dataTransfer.setData('text/plain', node.id);
            tr.classList.add('dragging');
        };
        tr.ondragend = (e) => { tr.classList.remove('dragging'); };
        
        if (node.item_type === 'folder') {
            tr.ondragover = (e) => { e.preventDefault(); tr.classList.add('drag-over'); };
            tr.ondragleave = (e) => { tr.classList.remove('drag-over'); };
            tr.ondrop = async (e) => {
                e.preventDefault(); tr.classList.remove('drag-over');
                const draggedId = e.dataTransfer.getData('text/plain');
                if (draggedId && draggedId !== node.id) await moveNode(draggedId, node.id);
            };
        }
        
        const isFolder = node.item_type === 'folder';

        const urlCol = isFolder ? 
            `<span style="cursor: pointer; color: var(--color-foreground);" onclick="openFolder('${node.id}')">
                <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24" style="vertical-align: middle; margin-right: 8px; color: #FBBF24;"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"></path></svg>
                <strong>${node.description}</strong>
            </span>` 
            : `${node.target_url}`;
            
        if (isFolder) {
            tr.innerHTML = `
                <td style="color: var(--text-secondary); font-weight: 500;">${index + 1}</td>
                <td></td>
                <td></td>
                <td class="target-url">${urlCol}</td>
                <td><span class="tag-auto">📂 Group</span></td>
                <td style="display:flex; gap: 8px; justify-content: flex-end;">
                    <button class="action-btn" onclick="emptyFolder('${node.id}')" title="Empty Folder (Keep Folder, Delete URLs)">
                        <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
                        <span style="font-size: 10px; margin-left: 2px;">Empty</span>
                    </button>
                    <button class="action-btn" onclick="deleteProxy('${node.id}')" title="Delete Folder completely">
                        <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
                    </button>
                </td>
            `;
        } else {
            tr.innerHTML = `
                <td style="color: var(--text-secondary); font-weight: 500;">${index + 1}</td>
                <td>
                    <label class="switch">
                        <input type="checkbox" ${node.is_active ? 'checked' : ''} onchange="toggleProxy('${node.id}', this)">
                        <span class="slider"></span>
                    </label>
                </td>
                <td><strong>${node.local_port || '-'}</strong></td>
                <td class="target-url">${urlCol}</td>
                <td>${node.description && node.description.includes('Auto-discovered') ? `<span class="tag-auto">🤖 ${node.description}</span>` : (node.description || '-')}</td>
                <td style="display:flex; gap: 8px; justify-content: flex-end;">
                    ${node.local_port ? `<a href="http://localhost:${node.local_port}" target="_blank" class="action-btn" title="Open Local Link">
                        <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path></svg>
                    </a>` : ''}
                    <button class="action-btn" onclick="deleteProxy('${node.id}')" title="Delete">
                        <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
                    </button>
                </td>
            `;
        }
        tbody.appendChild(tr);
    });
}

function filterTable() {
    renderMainArea(); // Re-render Main area flatly when searching
}

window.moveNode = async function(nodeId, newParentId) {
    try {
        await fetch(`${API_BASE}/mappings/${nodeId}/move`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ parent_id: newParentId })
        });
        fetchMappings();
    } catch(e) {
        alert("Failed to move item");
    }
}

async function toggleProxy(id, checkbox) {
    checkbox.disabled = true;
    try {
        const res = await fetch(`${API_BASE}/mappings/${id}/toggle`, { method: 'POST' });
        const data = await res.json();
        if(!data.success) {
            alert(data.error);
            checkbox.checked = !checkbox.checked;
        } else {
            // Update local state without refresh
            const node = globalMappings.find(m => m.id === id);
            if (node) node.is_active = checkbox.checked;
        }
    } catch (e) {
        checkbox.checked = !checkbox.checked;
    } finally {
        checkbox.disabled = false;
    }
}

async function emptyFolder(id) {
    if(!confirm('Are you sure you want to delete ALL URLs inside this folder? The folder itself will remain.')) return;
    try {
        await fetch(`${API_BASE}/folders/${id}/empty`, { method: 'DELETE' });
        fetchMappings();
    } catch (e) {
        alert("Failed to empty folder");
    }
}

async function deleteProxy(id) {
    if(!confirm('Are you sure you want to delete this item?')) return;
    try {
        await fetch(`${API_BASE}/mappings/${id}`, { method: 'DELETE' });
        selectedRowIds.delete(id);
        toggleBulkActionBtn();
        fetchMappings();
    } catch (e) {
        alert("Failed to delete proxy");
    }
}

window.toggleBulkActionBtn = function() {
    const btn = document.getElementById('bulkDeleteBtn');
    if (selectedRowIds.size > 0) {
        btn.style.display = 'inline-block';
        btn.innerText = `Delete Selected (${selectedRowIds.size})`;
    } else {
        btn.style.display = 'none';
    }
}

window.deleteSelectedProxies = async function() {
    if (selectedRowIds.size === 0) return;
    if (!confirm(`Are you sure you want to delete ${selectedRowIds.size} items?`)) return;
    
    document.getElementById('bulkDeleteBtn').disabled = true;
    try {
        for (let id of selectedRowIds) {
            await fetch(`${API_BASE}/mappings/${id}`, { method: 'DELETE' });
        }
        selectedRowIds.clear();
        toggleBulkActionBtn();
        fetchMappings();
    } catch (e) {
        alert("Some deletions failed");
    } finally {
        document.getElementById('bulkDeleteBtn').disabled = false;
    }
}

window.toggleTheme = function() {
    const body = document.body;
    if (body.getAttribute('data-theme') === 'light') {
        body.removeAttribute('data-theme');
    } else {
        body.setAttribute('data-theme', 'light');
    }
}

function openModal() {
    document.getElementById('addModal').classList.add('active');
}

function closeModal() {
    document.getElementById('addModal').classList.remove('active');
    document.getElementById('localPort').value = '';
    document.getElementById('targetUrl').value = '';
    document.getElementById('description').value = '';
}

async function submitProxy() {
    const port = document.getElementById('localPort').value;
    const url = document.getElementById('targetUrl').value;
    const desc = document.getElementById('description').value;
    
    if(!port || !url) {
        alert("Port and Target URL are required");
        return;
    }
    
    try {
        const res = await fetch(`${API_BASE}/mappings`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ local_port: parseInt(port), target_url: url, description: desc })
        });
        const data = await res.json();
        if(data.success) {
            closeModal();
            fetchMappings();
        } else {
            alert(data.error || 'Failed to create proxy');
        }
    } catch (e) {
        alert("Error creating proxy");
    }
}

// Support dropping items into the breadcrumb 'Home' or parents
document.getElementById('breadcrumbs').ondragover = (e) => { e.preventDefault(); };
document.getElementById('breadcrumbs').ondrop = async (e) => {
    e.preventDefault();
    const draggedId = e.dataTransfer.getData('text/plain');
    if (draggedId) {
        let target = e.target;
        if (target.classList.contains('breadcrumb-item')) {
            if (target.innerText === 'Home') {
                await moveNode(draggedId, null);
            }
        }
    }
}

function openFolderModal() {
    document.getElementById('addFolderModal').classList.add('active');
}

function closeFolderModal() {
    document.getElementById('addFolderModal').classList.remove('active');
    document.getElementById('folderName').value = '';
}

async function submitFolder() {
    const name = document.getElementById('folderName').value;
    if(!name) {
        alert("Folder Name is required");
        return;
    }
    try {
        const res = await fetch(`${API_BASE}/folders`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: name, parent_id: currentFolderId })
        });
        const data = await res.json();
        if(data.success) {
            closeFolderModal();
            fetchMappings();
        } else {
            alert(data.error || 'Failed to create folder');
        }
    } catch (e) {
        alert("Error creating folder");
    }
}

fetchMappings();
