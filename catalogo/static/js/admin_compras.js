const state = {
  token: localStorage.getItem('admin_pos_token') || '',
  refresh: localStorage.getItem('admin_pos_refresh') || '',
  categorias: [],
  mezcales: [],
  promociones: [],
  usuarios: [],
  compras: [],
  resenas: []
};

const API = {
  token: '/api/token/',
  reporte: '/api/reporte-ventas/',
  categorias: '/api/categorias/',
  mezcales: '/api/mezcales/',
  promociones: '/api/promociones/',
  usuarios: '/api/usuarios/',
  compras: '/api/compras/',
  resenas: '/api/resenas/',
  chatbot: '/api/chatbot/'
};

function money(n) {
  const v = Number(n || 0);
  return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(v);
}

async function api(url, options = {}, _retry = false) {
  const isForm = options.body instanceof FormData;
  const headers = {
    ...(isForm ? {} : { 'Content-Type': 'application/json' }),
    ...(options.headers || {})
  };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  const res = await fetch(url, { ...options, headers });

  if (res.status === 401 && !_retry && state.refresh) {
    try {
      const rr = await fetch('/api/token/refresh/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh: state.refresh })
      });
      if (rr.ok) {
        const d = await rr.json();
        setAuth(d.access, state.refresh);
        return api(url, options, true);
      }
    } catch (_) {}
    logout();
    throw new Error('Sesión expirada. Por favor inicia sesión nuevamente.');
  }

  if (!res.ok) {
    const txt = await res.text();
    throw new Error(txt || `HTTP ${res.status}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

function setAuth(access, refresh) {
  state.token = access || '';
  state.refresh = refresh || '';
  localStorage.setItem('admin_pos_token', state.token);
  localStorage.setItem('admin_pos_refresh', state.refresh);
}

function logout() {
  setAuth('', '');
  document.getElementById('app').classList.add('hidden');
  document.getElementById('login').classList.remove('hidden');
}

function showView(name) {
  document.querySelectorAll('.menu button[data-view]').forEach(b => b.classList.toggle('active', b.dataset.view === name));
  ['reporte','catalogos','articulos','promociones','usuarios','compras','resenas'].forEach(v => {
    document.getElementById(`view-${v}`).classList.toggle('hidden', v !== name);
  });
  const titles = {
    reporte: 'Reporte de ventas',
    catalogos: 'Categorías',
    articulos: 'Artículos',
    promociones: 'Promociones',
    usuarios: 'Usuarios',
    compras: 'Historial de Compras',
    resenas: 'Reseñas y Valoraciones'
  };
  document.getElementById('viewTitle').textContent = titles[name] || 'Administración';
  
  if(name==='reporte') loadReporte();
  if(name==='catalogos') loadCatalogos();
  if(name==='articulos') loadArticulos();
  if(name==='promociones') loadPromociones();
  if(name==='usuarios') loadUsuarios();
  if(name==='compras') loadCompras();
  if(name==='resenas') loadResenas();
}

// ================= VISTA REPORTE =================
async function loadReporte() {
  const target = document.getElementById('view-reporte');
  target.innerHTML = '<p>Cargando reporte...</p>';
  try {
    const data = await api(API.reporte);
    target.innerHTML = `
      <article class="card span-4 kpi"><h3>Total ventas</h3><p>${money(data.kpis?.total_ventas)}</p></article>
      <article class="card span-4 kpi"><h3>Total órdenes</h3><p>${data.kpis?.total_ordenes || 0}</p></article>
      <article class="card span-4 kpi"><h3>Ticket promedio</h3><p>${money(data.kpis?.ticket_promedio)}</p></article>
      <article class="card span-6">
        <h3>Productos más vendidos</h3>
        <canvas id="chartProductos" style="max-height:260px"></canvas>
      </article>
      <article class="card span-6">
        <h3>Clientes que más compran</h3>
        <canvas id="chartClientes" style="max-height:260px"></canvas>
      </article>
      <article class="card span-12">
        <h3>Productos mejor valorados</h3>
        <canvas id="chartValorados" style="max-height:260px"></canvas>
      </article>
    `;
    const PALETTE = ['#5d3f2b','#8a6441','#c2995b','#d4b896','#e8d5b8','#3b271b','#9b7a54','#b89170'];

    if (document.getElementById('chartProductos')) {
      new Chart(document.getElementById('chartProductos'), {
        type: 'bar',
        data: {
          labels: data.top_articulos?.length ? data.top_articulos.map(x => x.mezcal__nombre || 'Sin nombre') : ['Sin datos'],
          datasets: [{ label: 'Unidades vendidas',
            data: data.top_articulos?.length ? data.top_articulos.map(x => x.cantidad_vendida) : [0],
            backgroundColor: PALETTE, borderRadius: 5, borderSkipped: false }]
        },
        options: { indexAxis: 'y', responsive: true,
          plugins: { legend: { display: false } },
          scales: { x: { beginAtZero: true, grid: { color: '#ede0cc' } }, y: { grid: { display: false } } }
        }
      });
    }

    if (document.getElementById('chartClientes')) {
      new Chart(document.getElementById('chartClientes'), {
        type: 'doughnut',
        data: {
          labels: data.ventas_por_usuario?.length ? data.ventas_por_usuario.map(x => x.usuario__username) : ['Sin datos'],
          datasets: [{ data: data.ventas_por_usuario?.length ? data.ventas_por_usuario.map(x => Number(x.total_gastado)) : [1],
            backgroundColor: data.ventas_por_usuario?.length ? PALETTE : ['#d8c7b2'], borderWidth: 2, borderColor: '#f7f2e7' }]
        },
        options: { responsive: true,
          plugins: {
            legend: { position: 'right', labels: { font: { family: 'Georgia, serif', size: 12 }, color: '#3b271b', padding: 14 } },
            tooltip: { callbacks: { label: ctx => ` ${ctx.label}: ${money(ctx.raw)}` } }
          }
        }
      });
    }

    const valorados = data.productos_valorados || [];
    if (document.getElementById('chartValorados')) {
      new Chart(document.getElementById('chartValorados'), {
        type: 'bar',
        data: {
          labels: valorados.length ? valorados.map(x => x.nombre) : ['Sin datos'],
          datasets: [{ label: 'Calificación promedio',
            data: valorados.length ? valorados.map(x => Number(x.promedio).toFixed(2)) : [0],
            backgroundColor: PALETTE, borderRadius: 5, borderSkipped: false }]
        },
        options: { responsive: true,
          plugins: { legend: { display: false },
            tooltip: { callbacks: { label: ctx => {
              const item = valorados[ctx.dataIndex];
              return item ? ` ${ctx.raw} / 5 (${item.num_calificaciones} reseñas)` : 'Sin datos';
            }}}
          },
          scales: { y: { beginAtZero: true, max: 5, grid: { color: '#ede0cc' } }, x: { grid: { display: false } } }
        }
      });
    }
  } catch(e) {
    target.innerHTML = `<p style="color:var(--danger)">Error al cargar reporte: ${e.message}</p>`;
  }
}

function renderTable(headers, rows) {
  if (!rows.length) return '<p style="color:var(--muted);padding:16px 0">Sin registros.</p>';
  return `<table><thead><tr>${headers.map(h => `<th>${h}</th>`).join('')}</tr></thead><tbody>${rows.map(r => `<tr>${r.map(c => `<td>${c ?? ''}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
}

// ===== HELPER SMART TABLE =====
const _n=s=>String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
const ST = {
  PER: 10, _s: {},
  g(id) { if(!this._s[id]) this._s[id]={page:1,q:''}; return this._s[id]; },
  filter(id, data, sFields, fKeys=[]) {
    const s=this.g(id); let r=data || [];
    if(s.q){const q=_n(s.q); r=r.filter(row=>sFields.some(f=>_n(row[f]).includes(q)));}
    fKeys.forEach(k=>{const v=s['f_'+k]; if(v!==undefined&&v!=='') r=r.filter(row=>String(row[k])===v);});
    return r;
  },
  page(id, rows) {
    const s=this.g(id),tot=Math.ceil(rows.length/this.PER)||1,p=Math.min(Math.max(s.page,1),tot);
    this._s[id].page=p; const from=(p-1)*this.PER;
    return {rows:rows.slice(from,from+this.PER),page:p,tot,from:from+1,to:Math.min(from+this.PER,rows.length),count:rows.length};
  },
  wrap(id, pg, headers, rows, filters=[]) {
    const s=this.g(id);
    const fh=filters.map(f=>`<select class="st-f" data-id="${id}" data-k="${f.k}"
      style="border:1px solid #c9a882;border-radius:8px;padding:7px 10px;background:#fdf8f1;font-size:13px;cursor:pointer">
      <option value="">${f.lbl}</option>
      ${f.opts.map(o=>`<option value="${o.v}" ${(s['f_'+f.k]||'')===(String(o.v))?'selected':''}>${o.l}</option>`).join('')}
    </select>`).join('');
    const pgs=pg.tot>1?[...Array(Math.min(pg.tot,8))].map((_,i)=>{const n=i+1,a=n===pg.page;
      return `<button class="st-pg" data-id="${id}" data-p="${n}"
        style="border:1px solid ${a?'transparent':'#d4b896'};background:${a?'linear-gradient(135deg,#5d3f2b,#8a6441)':'white'};color:${a?'white':'#5a4030'};border-radius:6px;padding:5px 11px;cursor:pointer;font-size:13px;font-weight:${a?700:400}">${n}</button>`;
    }).join(''):'';
    return `<div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:12px">
      <input class="st-q" data-id="${id}" value="${s.q||''}" placeholder="🔍 Buscar..."
        style="flex:1;min-width:180px;border:1px solid #c9a882;border-radius:20px;padding:8px 16px;background:#fdf8f1;font-size:13px">
      ${fh}
      <span style="font-size:12px;color:var(--muted);white-space:nowrap;margin-left:auto">${pg.count?`${pg.from}–${pg.to} de <strong>${pg.count}</strong>`:'Sin resultados'}</span>
    </div>
    ${renderTable(headers, rows)}
    ${pg.tot>1?`<div style="display:flex;gap:5px;flex-wrap:wrap;margin-top:12px;align-items:center"><span style="font-size:12px;color:var(--muted);margin-right:2px">Página:</span>${pgs}</div>`:''}`;
  }
};

const _SR={};
const _EDIT={},_CRUD_EDIT={},_CRUD_DEL={};

function actBtns(sec,id,nm){
  return `<div style="display:flex;gap:4px;white-space:nowrap"><button class="crud-edit btn" data-sec="${sec}" data-id="${id}" style="padding:3px 10px;font-size:11px;background:linear-gradient(135deg,#5d6b3f,#7a8a52);color:white">✏ Editar</button> <button class="crud-del btn danger" data-sec="${sec}" data-id="${id}" data-nm="${String(nm).replace(/"/g,'&quot;')}" style="padding:3px 10px;font-size:11px">✕ Borrar</button></div>`;
}

function activoBadge(val,type,id,field='activo'){
  const bg=val?'#4a6b3c':'#8d6a52';
  return `<button onclick="_tact('${type}',${id},${!val},'${field}')" title="${val?'Clic para desactivar':'Clic para activar'}"
    style="background:${bg};color:white;border:none;border-radius:10px;padding:3px 13px;font-size:11px;font-weight:700;cursor:pointer;letter-spacing:.3px"
    onmouseover="this.style.filter='brightness(1.12)'" onmouseout="this.style.filter=''"
  >${val?'✓ Activo':'✕ Inactivo'}</button>`;
}

window._tact = async (type,id,newVal,field) => {
  const ep={cats:API.categorias,arts:API.mezcales,proms:API.promociones,usrs:API.usuarios};
  const sk={cats:'categorias',arts:'mezcales',proms:'promociones',usrs:'usuarios'};

  if (type === 'cats' && newVal === false) {
    const activos = state.mezcales.filter(m => m.categoria === id && m.activo);
    if (activos.length > 0) {
      const cascada = confirm(
        `La categoría tiene ${activos.length} artículo(s) activo(s).\n\n` +
        `¿Desactivar también esos artículos?\n\n` +
        `Aceptar  →  desactiva categoría + artículos\n` +
        `Cancelar →  desactiva solo la categoría`
      );
      try {
        await api(`${API.categorias}${id}/`,{method:'PATCH',body:JSON.stringify({activo:false})});
        const cat=state.categorias.find(x=>x.id===id); if(cat) cat.activo=false;
        if (cascada) {
          for (const m of activos) {
            await api(`${API.mezcales}${m.id}/`,{method:'PATCH',body:JSON.stringify({activo:false})});
            m.activo=false;
          }
          _SR['st-arts']?.();
        }
        _SR['st-cats']?.();
        _refreshCatSelect();
      } catch(e){alert('Error: '+e.message);}
      return;
    }
  }

  if (type === 'cats' && newVal === true) {
    const inactivos = state.mezcales.filter(m => m.categoria === id && !m.activo);
    if (inactivos.length > 0) {
      const cascada = confirm(
        `La categoría tiene ${inactivos.length} artículo(s) inactivo(s).\n\n` +
        `¿Activar también esos artículos?\n\n` +
        `Aceptar  →  activa categoría + artículos\n` +
        `Cancelar →  activa solo la categoría`
      );
      try {
        await api(`${API.categorias}${id}/`,{method:'PATCH',body:JSON.stringify({activo:true})});
        const cat=state.categorias.find(x=>x.id===id); if(cat) cat.activo=true;
        if (cascada) {
          for (const m of inactivos) {
            await api(`${API.mezcales}${m.id}/`,{method:'PATCH',body:JSON.stringify({activo:true})});
            m.activo=true;
          }
          _SR['st-arts']?.();
        }
        _SR['st-cats']?.();
        _refreshCatSelect();
      } catch(e){alert('Error: '+e.message);}
      return;
    }
  }

  if (type === 'arts' && newVal === true) {
    const art = state.mezcales.find(x => x.id === id);
    if (art?.categoria) {
      const cat = state.categorias.find(c => c.id === art.categoria);
      if (cat && !cat.activo) {
        alert(`No se puede activar "${art.nombre}".\nSu categoría "${cat.nombre}" está inactiva.\nActiva primero la categoría.`);
        return;
      }
    }
  }

  try{
    await api(`${ep[type]}${id}/`,{method:'PATCH',body:JSON.stringify({[field]:newVal})});
    const item=state[sk[type]]?.find(x=>x.id===id);
    if(item) item[field]=newVal;
    _SR['st-'+type]?.();
    if(type==='cats') _refreshCatSelect();
  }catch(e){alert('Error al cambiar estado: '+e.message);}
};

function _refreshCatSelect() {
  const sel = document.querySelector('#formMezcal [name=categoria]');
  if (!sel) return;
  const current = sel.value;
  sel.innerHTML = `<option value="">Sin categoría</option>` +
    state.categorias.filter(c => c.activo)
      .map(c => `<option value="${c.id}"${String(c.id)===String(current)?' selected':''}>${c.nombre}</option>`)
      .join('');
}

document.addEventListener('click',e=>{
  if(e.target.classList.contains('crud-edit')){const{sec,id}=e.target.dataset;_CRUD_EDIT[sec]?.(+id);}
  if(e.target.classList.contains('crud-del')){const{sec,id,nm}=e.target.dataset;if(confirm(`¿Eliminar "${nm}"?\nEsta acción no se puede deshacer.`))_CRUD_DEL[sec]?.(+id);}
});

function _eMode(fid,tid,key){
  const form=document.getElementById(fid);if(!form)return;
  form.querySelector('[type=submit]').textContent='Actualizar';
  const tEl=tid?document.getElementById(tid):null; if(tEl)tEl.textContent='Editar registro';
  if(!form.querySelector('.crud-cancel')){
    const b=document.createElement('button');b.type='button';b.className='btn crud-cancel';b.textContent='Cancelar';
    b.style.cssText='background:#7a6a5d;color:white;margin-left:8px';
    const labels={cats:'Nueva categoría',arts:'Nuevo artículo (mezcal)',proms:'Nueva promoción',usrs:'Nuevo usuario'};
    b.onclick=()=>{
      delete _EDIT[key];
      form.reset();
      form.querySelector('[type=submit]').textContent='Guardar';
      if(tEl)tEl.textContent=labels[key]||'Nuevo';
      b.remove();
    };
    form.querySelector('.actions').appendChild(b);
  }
  form.scrollIntoView({behavior:'smooth',block:'start'});
}

document.addEventListener('input',e=>{
  if(!e.target.classList.contains('st-q'))return;
  const id=e.target.dataset.id;
  const val=e.target.value;
  const pos=e.target.selectionStart;
  ST._s[id]={...ST.g(id),q:val,page:1};
  _SR[id]?.();
  const inp=document.querySelector(`.st-q[data-id="${id}"]`);
  if(inp){inp.focus();try{inp.setSelectionRange(pos,pos);}catch(_){}}
});
document.addEventListener('change',e=>{if(!e.target.classList.contains('st-f'))return;const id=e.target.dataset.id,k=e.target.dataset.k;ST._s[id]={...ST.g(id),['f_'+k]:e.target.value,page:1};_SR[id]?.();});
document.addEventListener('click',e=>{if(!e.target.classList.contains('st-pg'))return;const id=e.target.dataset.id;ST._s[id]={...ST.g(id),page:Number(e.target.dataset.p)};_SR[id]?.();});

// ================= VISTA CATEGORIAS =================
async function loadCatalogos() {
  state.categorias = await api(API.categorias);
  const target = document.getElementById('view-catalogos');
  target.innerHTML = `
    <article class="card span-12">
      <h3 id="cats-form-title">Nueva categoría</h3>
      <form id="formCategoria">
        <div class="field"><label>Nombre</label><input name="nombre" required></div>
        <div class="field"><label>Activo</label><select name="activo"><option value="true">Sí</option><option value="false">No</option></select></div>
        <div class="field full"><label>Descripción</label><textarea name="descripcion"></textarea></div>
        <div class="field full actions"><button class="btn primary" type="submit">Guardar</button></div>
      </form>
    </article>
    <article class="card span-12">
      <h3>Catálogo de categorías</h3>
      <div id="st-cats-wrap"></div>
    </article>
  `;
  _SR['st-cats'] = () => {
    const f=ST.filter('st-cats',state.categorias,['nombre','descripcion'],['activo']);
    const pg=ST.page('st-cats',f);
    document.getElementById('st-cats-wrap').innerHTML = ST.wrap('st-cats',pg,
      ['ID','Nombre','Activo','Descripción','Acciones'],
      pg.rows.map(c=>[c.id,c.nombre,activoBadge(c.activo,'cats',c.id,'activo'),c.descripcion||'',actBtns('cats',c.id,c.nombre)]),
      [{k:'activo',lbl:'Estado',opts:[{v:'true',l:'Activos'},{v:'false',l:'Inactivos'}]}]
    );
  };
  _SR['st-cats']();

  _CRUD_EDIT['cats']=id=>{
    const c=state.categorias.find(x=>x.id===id);if(!c)return;
    const fm=document.getElementById('formCategoria');
    fm.nombre.value=c.nombre;fm.descripcion.value=c.descripcion||'';fm.activo.value=String(c.activo);
    _EDIT.cats=id;_eMode('formCategoria','cats-form-title','cats');
  };

  _CRUD_DEL['cats']=async id=>{
    try{await api(`${API.categorias}${id}/`,{method:'DELETE'});}catch(e){alert('Error: '+e.message);return;}
    await loadCatalogos();
  };

  document.getElementById('formCategoria').onsubmit = async (e) => {
    e.preventDefault();
    const data = {
      nombre: e.target.nombre.value,
      descripcion: e.target.descripcion.value,
      activo: e.target.activo.value === 'true'
    };
    const isEdit = !!_EDIT.cats;
    const url = isEdit ? `${API.categorias}${_EDIT.cats}/` : API.categorias;
    const method = isEdit ? 'PUT' : 'POST';
    try {
      await api(url, { method, body: JSON.stringify(data) });
      delete _EDIT.cats;
      e.target.reset();
      await loadCatalogos();
    } catch(err) { alert('Error: ' + err.message); }
  };
}

// ================= VISTA ARTICULOS =================
async function loadArticulos() {
  [state.categorias, state.mezcales] = await Promise.all([api(API.categorias), api(API.mezcales)]);
  const catOpts = state.categorias.filter(c => c.activo)
    .map(c => `<option value="${c.id}">${c.nombre}</option>`).join('');

  const target = document.getElementById('view-articulos');
  target.innerHTML = `
    <article class="card span-12">
      <h3 id="arts-form-title">Nuevo artículo (mezcal)</h3>
      <form id="formMezcal" enctype="multipart/form-data">
        <div class="field"><label>Nombre</label><input name="nombre" required></div>
        <div class="field"><label>Categoría</label><select name="categoria"><option value="">Sin categoría</option>${catOpts}</select></div>
        <div class="field"><label>Tipo de agave</label><input name="tipo_agave" placeholder="Espadín, Tobalá..."></div>
        <div class="field"><label>Porcentaje de alcohol (%)</label><input name="porcentaje_alcohol" type="number" step="0.1"></div>
        <div class="field"><label>Precio ($ MXN)</label><input name="precio" type="number" step="0.01" required></div>
        <div class="field"><label>Stock disponible</label><input name="stock" type="number" required></div>
        <div class="field"><label>Imagen del producto</label><input name="imagen" type="file" accept="image/*"></div>
        <div class="field"><label>Activo</label><select name="activo"><option value="true">Sí</option><option value="false">No</option></select></div>
        <div class="field full"><label>Descripción</label><textarea name="descripcion"></textarea></div>
        <div class="field full actions"><button class="btn primary" type="submit">Guardar</button></div>
      </form>
    </article>
    <article class="card span-12">
      <h3>Catálogo de mezcales</h3>
      <div id="st-arts-wrap"></div>
    </article>
  `;

  _SR['st-arts'] = () => {
    const f=ST.filter('st-arts',state.mezcales,['nombre','tipo_agave','categoria_nombre'],['activo']);
    const pg=ST.page('st-arts',f);
    document.getElementById('st-arts-wrap').innerHTML = ST.wrap('st-arts',pg,
      ['Foto','Nombre','Categoría','Agave','Alc.','Precio','Stock','Activo','Acciones'],
      pg.rows.map(m=>[
        m.imagen ? `<img src="${m.imagen}" class="img-thumb" alt="${m.nombre}">` : '📷',
        m.nombre, m.categoria_nombre || 'Sin cat.', m.tipo_agave || '-',
        m.porcentaje_alcohol ? `${m.porcentaje_alcohol}%` : '-',
        money(m.precio), m.stock,
        activoBadge(m.activo,'arts',m.id,'activo'),
        actBtns('arts',m.id,m.nombre)
      ]),
      [{k:'activo',lbl:'Estado',opts:[{v:'true',l:'Activos'},{v:'false',l:'Inactivos'}]}]
    );
  };
  _SR['st-arts']();

  _CRUD_EDIT['arts']=id=>{
    const m=state.mezcales.find(x=>x.id===id);if(!m)return;
    const fm=document.getElementById('formMezcal');
    fm.nombre.value=m.nombre;
    _refreshCatSelect();
    fm.categoria.value=m.categoria||'';
    fm.tipo_agave.value=m.tipo_agave||'';
    fm.porcentaje_alcohol.value=m.porcentaje_alcohol||'';
    fm.precio.value=m.precio;
    fm.stock.value=m.stock;
    fm.activo.value=String(m.activo);
    fm.descripcion.value=m.descripcion||'';
    _EDIT.arts=id;_eMode('formMezcal','arts-form-title','arts');
  };

  _CRUD_DEL['arts']=async id=>{
    try{await api(`${API.mezcales}${id}/`,{method:'DELETE'});}catch(e){alert('Error: '+e.message);return;}
    await loadArticulos();
  };

  document.getElementById('formMezcal').onsubmit = async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    if(!e.target.imagen.files.length) formData.delete('imagen');
    formData.set('activo', e.target.activo.value);

    const isEdit = !!_EDIT.arts;
    const url = isEdit ? `${API.mezcales}${_EDIT.arts}/` : API.mezcales;
    const method = isEdit ? 'PATCH' : 'POST';

    try {
      await api(url, { method, body: formData });
      delete _EDIT.arts;
      e.target.reset();
      await loadArticulos();
    } catch(err) { alert('Error: ' + err.message); }
  };
}

// ================= VISTA PROMOCIONES =================
async function loadPromociones() {
  if (!state.mezcales.length) state.mezcales = await api(API.mezcales);
  state.promociones = await api(API.promociones);
  const mezcalOpts = state.mezcales
    .map(m => `<option value="${m.id}">${m.nombre}</option>`).join('');

  const target = document.getElementById('view-promociones');
  target.innerHTML = `
    <article class="card span-12">
      <h3 id="proms-form-title">Nueva promoción</h3>
      <form id="formPromocion">
        <div class="field"><label>Título</label><input name="titulo" required></div>
        <div class="field">
          <label>Artículo (mezcal)</label>
          <select name="mezcal"><option value="">General (sin artículo específico)</option>${mezcalOpts}</select>
        </div>
        <div class="field full" id="promMezcalPreview" style="display:none">
          <img id="promMezcalPreviewImg" src="" style="height:70px;border-radius:6px;border:1px solid var(--line);object-fit:cover">
        </div>
        <div class="field"><label>Porcentaje Descuento (%)</label><input name="descuento_porcentaje" type="number" min="1" max="100" required></div>
        <div class="field"><label>Fecha Inicio</label><input name="fecha_inicio" type="date" required></div>
        <div class="field"><label>Fecha Fin</label><input name="fecha_fin" type="date" required></div>
        <div class="field"><label>Activa</label><select name="activa"><option value="true">Sí</option><option value="false">No</option></select></div>
        <div class="field full"><label>Descripción</label><textarea name="descripcion"></textarea></div>
        <div class="field full actions"><button class="btn primary" type="submit">Guardar</button></div>
      </form>
    </article>
    <article class="card span-12">
      <h3>Lista de promociones</h3>
      <div id="st-proms-wrap"></div>
    </article>
  `;

  // Preview de imagen al elegir un mezcal
  const selMezcal = document.querySelector('#formPromocion [name=mezcal]');
  const previewBox = document.getElementById('promMezcalPreview');
  const previewImg = document.getElementById('promMezcalPreviewImg');
  selMezcal.addEventListener('change', () => {
    const m = state.mezcales.find(x => String(x.id) === selMezcal.value);
    if (m && m.imagen) {
      previewImg.src = m.imagen;
      previewBox.style.display = 'block';
    } else {
      previewBox.style.display = 'none';
    }
  });

  _SR['st-proms'] = () => {
    const f=ST.filter('st-proms',state.promociones,['titulo','descripcion','mezcal_nombre'],['activa']);
    const pg=ST.page('st-proms',f);
    document.getElementById('st-proms-wrap').innerHTML = ST.wrap('st-proms',pg,
      ['ID','Título','Artículo','Descuento','Inicio','Fin','Activa','Acciones'],
      pg.rows.map(p=>[
        p.id, p.titulo, p.mezcal_nombre || 'General', `${p.descuento_porcentaje}%`,
        p.fecha_inicio, p.fecha_fin,
        activoBadge(p.activa,'proms',p.id,'activa'),
        actBtns('proms',p.id,p.titulo)
      ]),
      [{k:'activa',lbl:'Estado',opts:[{v:'true',l:'Activas'},{v:'false',l:'Inactivas'}]}]
    );
  };
  _SR['st-proms']();

  _CRUD_EDIT['proms']=id=>{
    const p=state.promociones.find(x=>x.id===id);if(!p)return;
    const fm=document.getElementById('formPromocion');
    fm.titulo.value=p.titulo; fm.descuento_porcentaje.value=p.descuento_porcentaje;
    fm.fecha_inicio.value=p.fecha_inicio; fm.fecha_fin.value=p.fecha_fin;
    fm.activa.value=String(p.activa); fm.descripcion.value=p.descripcion||'';
    fm.mezcal.value = p.mezcal || '';
    fm.mezcal.dispatchEvent(new Event('change'));
    _EDIT.proms=id;_eMode('formPromocion','proms-form-title','proms');
  };

  _CRUD_DEL['proms']=async id=>{
    try{await api(`${API.promociones}${id}/`,{method:'DELETE'});}catch(e){alert('Error: '+e.message);return;}
    await loadPromociones();
  };

  document.getElementById('formPromocion').onsubmit = async (e) => {
    e.preventDefault();
    const data = {
      titulo: e.target.titulo.value,
      descuento_porcentaje: e.target.descuento_porcentaje.value,
      fecha_inicio: e.target.fecha_inicio.value,
      fecha_fin: e.target.fecha_fin.value,
      activa: e.target.activa.value === 'true',
      descripcion: e.target.descripcion.value,
      mezcal: e.target.mezcal.value || null
    };
    const isEdit = !!_EDIT.proms;
    const url = isEdit ? `${API.promociones}${_EDIT.proms}/` : API.promociones;
    const method = isEdit ? 'PUT' : 'POST';
    try {
      await api(url, { method, body: JSON.stringify(data) });
      delete _EDIT.proms;
      e.target.reset();
      previewBox.style.display = 'none';
      await loadPromociones();
    } catch(err) { alert('Error: ' + err.message); }
  };
}

// ================= VISTA USUARIOS =================
async function loadUsuarios() {
  state.usuarios = await api(API.usuarios);
  const target = document.getElementById('view-usuarios');
  target.innerHTML = `
    <article class="card span-12">
      <h3 id="usrs-form-title">Nuevo usuario</h3>
      <form id="formUsuario">
        <div class="field"><label>Username</label><input name="username" required></div>
        <div class="field"><label>Email</label><input name="email" type="email" required></div>
        <div class="field"><label>Nombre</label><input name="first_name"></div>
        <div class="field"><label>Apellido</label><input name="last_name"></div>
        <div class="field"><label>Rol</label><select name="rol"><option value="cliente">Cliente</option><option value="administrador">Administrador</option></select></div>
        <div class="field"><label>Contraseña</label><input name="password" type="password" placeholder="Solo al crear o cambiar"></div>
        <div class="field full actions"><button class="btn primary" type="submit">Guardar</button></div>
      </form>
    </article>
    <article class="card span-12">
      <h3>Lista de usuarios</h3>
      <div id="st-usrs-wrap"></div>
    </article>
  `;

  _SR['st-usrs'] = () => {
    const f=ST.filter('st-usrs',state.usuarios,['username','email','first_name','last_name'],['rol']);
    const pg=ST.page('st-usrs',f);
    document.getElementById('st-usrs-wrap').innerHTML = ST.wrap('st-usrs',pg,
      ['ID','Username','Nombre Completo','Email','Rol','Acciones'],
      pg.rows.map(u=>[
        u.id, u.username, `${u.first_name || ''} ${u.last_name || ''}`.trim() || '-',
        u.email, `<span class="badge">${u.rol}</span>`,
        actBtns('usrs',u.id,u.username)
      ]),
      [{k:'rol',lbl:'Rol',opts:[{v:'cliente',l:'Clientes'},{v:'administrador',l:'Admins'}]}]
    );
  };
  _SR['st-usrs']();

  _CRUD_EDIT['usrs']=id=>{
    const u=state.usuarios.find(x=>x.id===id);if(!u)return;
    const fm=document.getElementById('formUsuario');
    fm.username.value=u.username; fm.email.value=u.email;
    fm.first_name.value=u.first_name||''; fm.last_name.value=u.last_name||'';
    fm.rol.value=u.rol||'cliente'; fm.password.value='';
    _EDIT.usrs=id;_eMode('formUsuario','usrs-form-title','usrs');
  };

  _CRUD_DEL['usrs']=async id=>{
    try{await api(`${API.usuarios}${id}/`,{method:'DELETE'});}catch(e){alert('Error: '+e.message);return;}
    await loadUsuarios();
  };

  document.getElementById('formUsuario').onsubmit = async (e) => {
    e.preventDefault();
    const data = {
      username: e.target.username.value,
      email: e.target.email.value,
      first_name: e.target.first_name.value,
      last_name: e.target.last_name.value,
      rol: e.target.rol.value
    };
    if (e.target.password.value) data.password = e.target.password.value;

    const isEdit = !!_EDIT.usrs;
    const url = isEdit ? `${API.usuarios}${_EDIT.usrs}/` : API.usuarios;
    const method = isEdit ? 'PATCH' : 'POST';
    try {
      await api(url, { method, body: JSON.stringify(data) });
      delete _EDIT.usrs;
      e.target.reset();
      await loadUsuarios();
    } catch(err) { alert('Error: ' + err.message); }
  };
}

function estadoActualDeOrden(estado) {
  if (estado === 'pendiente') return 'pendiente';
  if (estado === 'cancelado') return 'cancelado';
  return 'pagado'; // pagado, recibido, repartiendo, entregado -> se agrupan como "pagado"
}

function pedidoDeOrden(estado) {
  const map = { pagado: 'Recibido', recibido: 'Recibido', repartiendo: 'En reparto', entregado: 'Entregado' };
  return map[estado] || null; // null = no aplica (pendiente o cancelado)
}

// ================= VISTA COMPRAS =================
async function loadCompras() {
  state.compras = await api(API.compras);
  const target = document.getElementById('view-compras');
  if (!target) return;

  target.innerHTML = `
    <article class="card span-12">
      <h3>Historial de compras y órdenes</h3>
      <div id="st-compras-wrap"></div>
    </article>
  `;

  state.compras = state.compras.map(o => ({
    ...o,
    metodo_pago_normalizado: obtenerMetodoPago(o),
    estado_actual: estadoActualDeOrden(o.estado || 'pendiente'),
    pedido_display: pedidoDeOrden(o.estado || 'pendiente')
  }));

  _SR['st-compras'] = () => {
    const f = ST.filter('st-compras', state.compras, ['id', 'usuario_username'], ['estado_actual', 'metodo_pago_normalizado']);
    const pg = ST.page('st-compras', f);
    const wrapEl = document.getElementById('st-compras-wrap');

    if (wrapEl) {
      wrapEl.innerHTML = ST.wrap('st-compras', pg,
        ['ID Órden', 'Cliente', 'Fecha', 'Total', 'Método Pago', 'Estado Actual', 'Pedido', 'Acciones de Gestión'],
        pg.rows.map(o => {
          const fecha = o.creado_en || o.fecha ? new Date(o.creado_en || o.fecha).toLocaleString('es-MX') : '-';
          const metodoDisplay = o.metodo_pago_normalizado.toUpperCase();

          return [
            `#${o.id}`,
            o.usuario_username || o.usuario || 'Cliente',
            fecha,
            money(o.total),
            `<strong style="color: ${metodoDisplay === 'TARJETA' ? '#2b6cb0' : '#2f855a'}">${metodoDisplay}</strong>`,
            renderEstadoBadge(o.estado_actual),
            o.pedido_display ? renderPedidoBadge(o.pedido_display, o.id, o.estado) : '<span style="color:var(--muted);font-size:12px">—</span>',
            renderAccionesOrden(o)
          ];
        }),
        [
          {
            k: 'metodo_pago_normalizado',
            lbl: 'Método Pago',
            opts: [
              { v: 'efectivo', l: 'Efectivo' },
              { v: 'tarjeta', l: 'Tarjeta' }
            ]
          },
          {
            k: 'estado_actual',
            lbl: 'Estado Actual',
            opts: [
              { v: 'pendiente', l: 'Pendiente' },
              { v: 'pagado', l: 'Pagado' },
              { v: 'cancelado', l: 'Cancelado' }
            ]
          }
        ]
      );
    }
  };
  _SR['st-compras']();
}

// Función helper para detectar correctamente cómo viene el método desde el backend
function obtenerMetodoPago(orden) {
  const valor = orden.metodo_pago || 'efectivo';
  const str = String(valor).toLowerCase().trim();

  if (str.includes('tarjeta') || str.includes('card') || str.includes('stripe') || str.includes('paypal')) {
    return 'tarjeta';
  }
  return 'efectivo';
}

// Badges visuales
function renderEstadoBadge(estado) {
  const colors = {
    pendiente: 'background:#d9822b;color:white;',
    pagado: 'background:#2f855a;color:white;',
    cancelado: 'background:#c53030;color:white;'
  };
  const style = colors[estado] || 'background:#718096;color:white;';
  return `<span style="${style}padding:4px 10px;border-radius:12px;font-size:11px;font-weight:700;text-transform:uppercase;">${estado}</span>`;
}

function renderPedidoBadge(pedido, ordenId, estadoRaw) {
  const colors = {
    'Recibido': 'background:#2b6cb0;color:white;',
    'En reparto': 'background:#b7791f;color:white;',
    'Entregado': 'background:#2f855a;color:white;'
  };
  const style = colors[pedido] || 'background:#718096;color:white;';

  const siguienteEstado = {
    'pagado': 'repartiendo',
    'recibido': 'repartiendo',
    'repartiendo': 'entregado'
  }[estadoRaw];

  if (!siguienteEstado) {
    return `<span style="${style}padding:4px 10px;border-radius:12px;font-size:11px;font-weight:700;text-transform:uppercase;">${pedido}</span>`;
  }

  return `<button onclick="avanzarPedido(${ordenId}, '${siguienteEstado}')"
    style="${style}padding:4px 10px;border-radius:12px;font-size:11px;font-weight:700;text-transform:uppercase;border:none;cursor:pointer;"
    onmouseover="this.style.filter='brightness(1.12)'" onmouseout="this.style.filter=''"
    title="Clic para avanzar el estado del pedido"
  >${pedido} →</button>`;
}

// Acciones de Gestión
function renderAccionesOrden(o) {
  const estado = o.estado || 'pendiente';

  if (estado !== 'pendiente') {
    return `<span style="font-size:12px;color:var(--muted)">Sin acciones</span>`;
  }

  return `
    <div style="display:flex; gap:6px;">
      <button class="btn success" onclick="aceptarOrden(${o.id})" style="padding:4px 10px;font-size:11px">Aceptar</button>
      <button class="btn danger" onclick="rechazarOrden(${o.id})" style="padding:4px 10px;font-size:11px">Rechazar</button>
    </div>
  `;
}

// Funciones globales
window.aceptarOrden = async function(id) {
  if (!confirm(`¿Aceptar la orden #${id}? Se marcará como Pagada.`)) return;
  try {
    await api(`${API.compras}${id}/`, {
      method: 'PATCH',
      body: JSON.stringify({ estado: 'pagado' })
    });
    await loadCompras();
  } catch(e) {
    alert('Error al aceptar la orden: ' + e.message);
  }
};

window.rechazarOrden = async function(id) {
  if (!confirm(`¿Rechazar la orden #${id}? Se marcará como Cancelada.`)) return;
  try {
    await api(`${API.compras}${id}/`, {
      method: 'PATCH',
      body: JSON.stringify({ estado: 'cancelado' })
    });
    await loadCompras();
  } catch(e) {
    alert('Error al rechazar la orden: ' + e.message);
  }
};

// ================= FUNCIONES GLOBALES DE GESTIÓN =================

window.aceptarOrden = async function(id) {
  if (!confirm(`¿Aceptar la orden #${id}? Se marcará como Pagada.`)) return;
  try {
    await api(`${API.compras}${id}/`, {
      method: 'PATCH',
      body: JSON.stringify({ estado: 'pagado' })
    });
    await loadCompras();
  } catch(e) {
    alert('Error al aceptar la orden: ' + e.message);
  }
};

window.rechazarOrden = async function(id) {
  if (!confirm(`¿Rechazar la orden #${id}? Se marcará como Cancelada.`)) return;
  try {
    await api(`${API.compras}${id}/`, {
      method: 'PATCH',
      body: JSON.stringify({ estado: 'cancelado' })
    });
    await loadCompras();
  } catch(e) {
    alert('Error al rechazar la orden: ' + e.message);
  }
};

window.avanzarPedido = async function(id, nuevoEstado) {
  const labels = { repartiendo: 'En reparto', entregado: 'Entregado' };
  if (!confirm(`¿Marcar el pedido #${id} como "${labels[nuevoEstado]}"?`)) return;
  try {
    await api(`${API.compras}${id}/`, {
      method: 'PATCH',
      body: JSON.stringify({ estado: nuevoEstado })
    });
    await loadCompras();
  } catch (e) {
    alert('Error al actualizar el pedido: ' + e.message);
  }
};

// ================= VISTA RESEÑAS =================
async function loadResenas() {
  state.resenas = await api(API.resenas);
  const target = document.getElementById('view-resenas');
  target.innerHTML = `
    <article class="card span-12">
      <h3>Reseñas y valoraciones de clientes</h3>
      <div id="st-resenas-wrap"></div>
    </article>
  `;

  _SR['st-resenas'] = () => {
    const f=ST.filter('st-resenas',state.resenas,['mezcal_nombre','usuario_username','comentario'],['calificacion']);
    const pg=ST.page('st-resenas',f);
    document.getElementById('st-resenas-wrap').innerHTML = ST.wrap('st-resenas',pg,
      ['ID','Producto','Cliente','Calificación','Comentario','Fecha'],
      pg.rows.map(r => [
        r.id,
        r.mezcal_nombre || 'Producto',
        r.usuario_username || 'Cliente',
        '⭐'.repeat(r.calificacion || 5),
        r.comentario || 'Sin comentario',
        r.creado_en ? new Date(r.creado_en).toLocaleDateString('es-MX') : '-'
      ]),
      [{k:'calificacion',lbl:'Calificación',opts:[
        {v:'5',l:'5 Estrellas'},{v:'4',l:'4 Estrellas'},{v:'3',l:'3 Estrellas'},{v:'2',l:'2 Estrellas'},{v:'1',l:'1 Estrella'}
      ]}]
    );
  };
  _SR['st-resenas']();
}

// ================= INICIALIZACIÓN Y EVENTOS =================
document.addEventListener('DOMContentLoaded', () => {
  // Comprobar autenticación inicial
  if (state.token) {
    document.getElementById('login').classList.add('hidden');
    document.getElementById('app').classList.remove('hidden');
    showView('reporte');
  }

  // Formulario de Login
  document.getElementById('loginForm').onsubmit = async (e) => {
    e.preventDefault();
    const statusDiv = document.getElementById('loginStatus');
    statusDiv.textContent = 'Autenticando...';
    try {
      const res = await fetch(API.token, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: e.target.username.value,
          password: e.target.password.value
        })
      });
      if (!res.ok) throw new Error('Credenciales inválidas');
      const data = await res.json();
      setAuth(data.access, data.refresh);
      statusDiv.textContent = '';
      document.getElementById('login').classList.add('hidden');
      document.getElementById('app').classList.remove('hidden');
      showView('reporte');
    } catch(err) {
      statusDiv.textContent = err.message;
    }
  };

  // Botón de Cerrar Sesión
  document.getElementById('logoutBtn').onclick = logout;

  // Botones de Navegación Menú
  document.querySelectorAll('.menu button[data-view]').forEach(btn => {
    btn.onclick = () => showView(btn.dataset.view);
  });

  // Widget Asistente / Chatbot
  const chatBtn = document.getElementById('chatBtn');
  const chatPanel = document.getElementById('chatPanel');
  const chatCloseBtn = document.getElementById('chatCloseBtn');
  const chatInput = document.getElementById('chatInput');
  const chatSendBtn = document.getElementById('chatSendBtn');
  const chatMessages = document.getElementById('chatMessages');

  chatBtn.onclick = () => chatPanel.classList.toggle('hidden');
  chatCloseBtn.onclick = () => chatPanel.classList.add('hidden');

  const sendChatMessage = async () => {
    const text = chatInput.value.trim();
    if (!text) return;

    chatMessages.innerHTML += `<div class="chat-msg chat-msg-user">${text}</div>`;
    chatInput.value = '';
    chatMessages.scrollTop = chatMessages.scrollHeight;

    const typingId = 'typing-' + Date.now();
    chatMessages.innerHTML += `<div id="${typingId}" class="chat-msg chat-msg-bot chat-typing">Pensando...</div>`;
    chatMessages.scrollTop = chatMessages.scrollHeight;

    try {
      const res = await api(API.chatbot, {
        method: 'POST',
        body: JSON.stringify({ mensaje: text })
      });
      document.getElementById(typingId)?.remove();
      chatMessages.innerHTML += `<div class="chat-msg chat-msg-bot">${res.respuesta || 'Sin respuesta'}</div>`;
    } catch(e) {
      document.getElementById(typingId)?.remove();
      chatMessages.innerHTML += `<div class="chat-msg chat-msg-bot" style="color:var(--danger)">Error: ${e.message}</div>`;
    }
    chatMessages.scrollTop = chatMessages.scrollHeight;
  };

  chatSendBtn.onclick = sendChatMessage;
  chatInput.onkeypress = (e) => { if (e.key === 'Enter') sendChatMessage(); };
});