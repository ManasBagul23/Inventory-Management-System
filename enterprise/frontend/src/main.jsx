import React, {useEffect, useState} from 'react';
import {createRoot} from 'react-dom/client';
import './styles.css';

async function api(path, data, csrf) {
  const response = await fetch('/api/' + path, data === undefined ? {} : {
    method: 'POST',
    headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf},
    body: JSON.stringify(data),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'The request could not be completed.');
  return result;
}

const currency = new Intl.NumberFormat('en-US', {style: 'currency', currency: 'USD'});
const dateFormat = new Intl.DateTimeFormat(undefined, {dateStyle: 'medium', timeStyle: 'short'});

function Field({label, children}) {
  return <label>{label}{children}</label>;
}

function Form({children, submit, onSubmit, className}) {
  const [pending, setPending] = useState(false);
  async function handleSubmit(event) {
    event.preventDefault();
    const form = event.currentTarget;
    setPending(true);
    try {
      if (await onSubmit(Object.fromEntries(new FormData(form)))) form.reset();
    } finally {
      setPending(false);
    }
  }
  return <form className={className} onSubmit={handleSubmit}>
    <fieldset disabled={pending}>{children}<button type="submit">{pending ? 'Saving…' : submit}</button></fieldset>
  </form>;
}

function Table({columns, rows, empty}) {
  if (!rows.length) return <p className="empty">{empty}</p>;
  return <div className="table-scroll"><table>
    <thead><tr>{columns.map(column => <th key={column} scope="col">{column}</th>)}</tr></thead>
    <tbody>{rows.map(({id, cells}) => <tr key={id}>{cells.map((cell, index) => <td key={columns[index]}>{cell}</td>)}</tr>)}</tbody>
  </table></div>;
}

function Stock({data, mutate}) {
  return <>
    <div className="panel">
      <div className="panel-title"><h2>Stock on hand</h2><span>{data.products.length} SKUs</span></div>
      <Table columns={['SKU', 'Product', 'On hand']} empty="Add a product to start tracking stock."
        rows={data.products.map(item => ({id: item.id, cells: [<code>{item.sku}</code>, item.name, item.stock]}))} />
    </div>
    <div className="form-grid">
      <section className="panel"><h2>Add a product</h2>
        <Form submit="Add product" onSubmit={fields => mutate('products/', fields, 'Product added.')}>
          <Field label="SKU"><input name="sku" required maxLength={32} /></Field>
          <Field label="Product name"><input name="name" required maxLength={120} /></Field>
        </Form>
      </section>
      <section className="panel"><h2>Record stock movement</h2>
        {data.products.length ? <Form submit="Record movement" onSubmit={({product, delta, note}) =>
          mutate('products/' + product + '/movement/', {delta: Number(delta), note}, 'Stock movement recorded.')}>
          <Field label="Product"><ProductSelect products={data.products} /></Field>
          <Field label="Quantity change"><input name="delta" type="number" min="-1000000" max="1000000" required placeholder="Use a minus sign to remove stock" /></Field>
          <Field label="Reason"><input name="note" required maxLength={160} /></Field>
        </Form> : <p className="empty">Add a product before recording stock movements.</p>}
      </section>
    </div>
    <section className="panel"><h2>Recent movements</h2>
      <Table columns={['SKU', 'Change', 'Reason', 'Recorded']} empty="No movements recorded."
        rows={data.movements.map(item => ({id: item.id, cells: [
          <code>{item.product__sku}</code>, item.delta > 0 ? '+' + item.delta : item.delta, item.note,
          dateFormat.format(new Date(item.created_at)),
        ]}))} />
    </section>
  </>;
}

function ProductSelect({products}) {
  return <select name="product" required>{products.map(item => <option key={item.id} value={item.id}>{item.sku} · {item.name}</option>)}</select>;
}

function Quotations({data, buyer, mutate}) {
  return <>
    {buyer && <section className="panel"><h2>Request a quotation</h2>
      {data.products.length && data.suppliers.length ? <Form className="inline" submit="Send request" onSubmit={({product, supplier, quantity}) =>
        mutate('quotations/', {product: Number(product), supplier: Number(supplier), quantity: Number(quantity)}, 'Quotation requested.')}>
        <Field label="Product"><ProductSelect products={data.products} /></Field>
        <Field label="Supplier"><select name="supplier" required>{data.suppliers.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></Field>
        <Field label="Quantity"><input name="quantity" type="number" min="1" max="1000000000" required /></Field>
      </Form> : <p className="empty">A product and supplier are required to request a quotation.</p>}
    </section>}
    <section className="panel"><h2>{buyer ? 'Quotation history' : 'Your quotation requests'}</h2>
      <div className="quotes">
        {data.quotations.length ? data.quotations.map(item => <article className="quote" key={item.id}>
          <div className="panel-title"><h3>{item.product}</h3><span className={'status ' + item.status}>{item.status}</span></div>
          <p>{item.sku} · {item.quantity} units · {item.supplier}</p>
          {item.unit_price && <strong>{currency.format(item.unit_price)} per unit</strong>}
          {buyer && item.can_accept && <Form submit="Accept quote" onSubmit={() =>
            mutate('quotations/' + item.id + '/accept/', {}, 'Quotation accepted.')} />}
          {!buyer && item.status === 'requested' && <Form submit="Submit quote" onSubmit={fields =>
            mutate('quotations/' + item.id + '/quote/', fields, 'Quote submitted.')}>
            <Field label="Unit price (USD)"><input name="price" inputMode="decimal" type="number" min=".01" max="99999999.99" step=".01" required /></Field>
          </Form>}
        </article>) : <p className="empty">No quotation requests yet.</p>}
      </div>
    </section>
  </>;
}

function Notifications({items, mutate}) {
  return <section className="panel"><h2>Notifications</h2>
    {items.length ? <ul className="notices">{items.map(item => <li key={item.id}>
      <div><strong>{item.job__message}</strong><small>{dateFormat.format(new Date(item.created_at))}</small></div>
      {item.read ? <span>Read</span> : <button className="secondary" onClick={() =>
        mutate('notifications/' + item.id + '/read/', {}, 'Notification marked as read.')}>Mark as read</button>}
    </li>)}</ul> : <p className="empty">New quotation activity will appear here.</p>}
  </section>;
}

function App() {
  const [session, setSession] = useState(null);
  const [data, setData] = useState(null);
  const [page, setPage] = useState('Stockroom');
  const [revision, setRevision] = useState(0);
  const [message, setMessage] = useState('');
  const [problem, setProblem] = useState('');

  useEffect(() => {
    api('session/').then(setSession).catch(error => setProblem(error.message));
  }, []);

  const role = session?.role;
  useEffect(() => {
    if (!role) return;
    let current = true;
    async function refresh() {
      try {
        const result = await api('workspace/');
        if (current) setData(result);
      } catch (error) {
        if (current) setProblem(error.message);
      }
    }
    refresh();
    const timer = setInterval(refresh, 8000);
    return () => { current = false; clearInterval(timer); };
  }, [role, revision]);

  async function perform(path, fields, after) {
    setProblem('');
    setMessage('');
    try {
      const result = await api(path, fields, session.csrf);
      after(result);
      return true;
    } catch (error) {
      setProblem(error.message);
      return false;
    }
  }

  function updateSession(fields) {
    return perform('session/', fields, result => {
      setData(null);
      setSession(result);
      setPage(result.role === 'supplier' ? 'Quotations' : 'Stockroom');
    });
  }

  function mutate(path, fields, notice) {
    return perform(path, fields, () => {
      setMessage(notice);
      setRevision(value => value + 1);
    });
  }

  if (!role) return <main className="login">
    <div className="login-copy"><span className="wordmark">Enterprise Inventory</span><h1>Stock and purchasing</h1><p>Track stock, request quotes, and follow supplier activity from one workspace.</p></div>
    <section className="panel"><h2>Sign in</h2>
      {problem && <p role="alert" className="error">{problem}</p>}
      {session ? <Form submit="Sign in" onSubmit={updateSession}>
        <Field label="Username"><input name="username" autoComplete="username" required /></Field>
        <Field label="Password"><input name="password" type="password" autoComplete="current-password" required /></Field>
      </Form> : !problem && <p role="status">Loading session…</p>}
    </section>
  </main>;

  const buyer = role === 'buyer';
  const unread = data?.notifications.filter(item => !item.read).length ?? 0;
  const pages = buyer ? ['Stockroom', 'Quotations', 'Notifications'] : ['Quotations', 'Notifications'];
  const activePage = pages.includes(page) ? page : pages[0];
  const stats = data && (buyer ? [
    ['Stock keeping units', data.products.length],
    ['Units on hand', data.products.reduce((total, item) => total + item.stock, 0)],
    ['Open quotations', data.quotations.filter(item => item.status !== 'accepted').length],
  ] : [
    ['Requests awaiting a price', data.quotations.filter(item => item.status === 'requested').length],
    ['Accepted quotes', data.quotations.filter(item => item.status === 'accepted').length],
    ['Unread notifications', unread],
  ]);

  return <>
    <header className="topbar"><div className="shell topbar-inner">
      <strong className="wordmark">Enterprise Inventory</strong>
      <span>{session.username} · {buyer ? 'Buyer' : 'Supplier'}</span>
      <button className="secondary" onClick={() => updateSession({action: 'logout'})}>Sign out</button>
    </div></header>
    <main className="shell workspace">
      <h1>{activePage}</h1>
      {stats && <dl className="metrics">{stats.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value.toLocaleString()}</dd></div>)}</dl>}
      <nav aria-label="Workspace sections">{pages.map(item => <button key={item} className="section-button"
        aria-current={item === activePage ? 'page' : undefined} onClick={() => { setPage(item); setMessage(''); setProblem(''); }}>
        {item}{item === 'Notifications' && unread > 0 ? ' (' + unread + ')' : ''}
      </button>)}</nav>
      {problem && <p role="alert" className="error">{problem}</p>}
      {message && <p role="status" className="success">{message}</p>}
      {!data && !problem && <p role="status">Loading workspace…</p>}
      {data && activePage === 'Stockroom' && <Stock data={data} mutate={mutate} />}
      {data && activePage === 'Quotations' && <Quotations data={data} buyer={buyer} mutate={mutate} />}
      {data && activePage === 'Notifications' && <Notifications items={data.notifications} mutate={mutate} />}
    </main>
  </>;
}

createRoot(document.getElementById('root')).render(<App />);
