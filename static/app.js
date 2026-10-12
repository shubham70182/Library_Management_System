const memberTokenKey = 'libraryMemberToken';
let memberToken = sessionStorage.getItem(memberTokenKey);
let memberIsSignedIn = Boolean(memberToken);
let librarianIsSignedIn = false;
let books = [];
let branches = [];
let members = [];

const api = {
  async request(path, options = {}) {
    const headers = new Headers(options.headers || {});
    if (options.body && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json');
    }
    if (memberIsSignedIn && memberToken && !headers.has('Authorization')) {
      headers.set('Authorization', `Bearer ${memberToken}`);
    }

    let response;
    try {
      response = await fetch(path, {
        ...options,
        headers,
        credentials: 'same-origin',
      });
    } catch {
      throw new Error('Could not reach the library server. Please try again.');
    }

    if (response.status === 204) return null;
    const text = await response.text();
    let data = {};
    if (text) {
      try {
        data = JSON.parse(text);
      } catch {
        throw new Error('The server returned an unexpected response.');
      }
    }
    if (!response.ok) {
      throw new Error(data.error?.message || 'The request could not be completed.');
    }
    return data;
  },

  get(path, options = {}) {
    return this.request(path, options);
  },

  post(path, payload, headers = {}) {
    return this.request(path, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
    });
  },
};

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

function setMessage(id, message = '', type = '') {
  const target = document.getElementById(id);
  if (!target) return;
  target.textContent = message;
  target.className = `form-message${type ? ` ${type}` : ''}`;
}

function setNotice(id, message = '', type = '') {
  const target = document.getElementById(id);
  if (!target) return;
  target.textContent = message;
  target.className = `notice${type ? ` ${type}` : ''}${message ? '' : ' hidden'}`;
}

function formatDate(value) {
  if (!value) return '—';
  const parsed = new Date(`${value}T00:00:00`);
  return Number.isNaN(parsed.getTime())
    ? value
    : new Intl.DateTimeFormat(undefined, { day: 'numeric', month: 'short', year: 'numeric' }).format(parsed);
}

function formatCurrency(amount) {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
  }).format(Number(amount));
}

function makeTable(headers, rows, emptyMessage = 'Nothing to show yet.') {
  if (!rows.length) {
    return element('p', 'empty-state', emptyMessage);
  }
  const wrapper = element('div', 'table-scroll');
  const table = element('table');
  const head = element('thead');
  const headerRow = element('tr');
  headers.forEach((label) => headerRow.append(element('th', '', label)));
  head.append(headerRow);
  const body = element('tbody');

  rows.forEach((row) => {
    const tableRow = element('tr');
    row.forEach((value) => {
      const cell = element('td');
      if (value instanceof Node) cell.append(value);
      else cell.textContent = value === null || value === undefined ? '—' : String(value);
      tableRow.append(cell);
    });
    body.append(tableRow);
  });
  table.append(head, body);
  wrapper.append(table);
  return wrapper;
}

function renderBooks() {
  const list = document.getElementById('bookList');
  const query = document.getElementById('searchInput').value.trim().toLowerCase();
  const visibleBooks = books.filter((book) => (
    `${book.title} ${book.authors || ''} ${book.isbn || ''}`.toLowerCase().includes(query)
  ));
  list.replaceChildren();

  if (!visibleBooks.length) {
    list.append(element('p', 'empty-state book-empty', query ? 'No books match your search.' : 'The catalogue is empty.'));
    return;
  }

  visibleBooks.forEach((book, index) => {
    const card = element('article', 'book-card');
    const cover = element('div', `book-cover cover-${index % 5}`);
    cover.append(element('span', 'cover-label', book.authors || 'CITY LIBRARY'));
    cover.append(element('strong', '', book.title));
    cover.append(element('span', 'cover-bottom', `NO. ${String(book.book_id).padStart(2, '0')}`));

    const details = element('div', 'book-details');
    details.append(element('h3', '', book.title));
    details.append(element('p', 'book-author', book.authors || 'Author not listed'));

    const meta = element('div', 'book-meta');
    meta.append(element('span', '', book.published_year || 'Year not listed'));
    if (book.isbn) meta.append(element('span', '', `ISBN ${book.isbn}`));
    details.append(meta);

    const availability = element(
      'span',
      Number(book.available_copies) > 0 ? 'availability available' : 'availability unavailable',
      Number(book.available_copies) > 0
        ? `${book.available_copies} available`
        : 'No copies available',
    );
    const copiesButton = element('button', 'text-button', 'View copies');
    copiesButton.type = 'button';
    copiesButton.addEventListener('click', () => showBookCopies(book));
    details.append(availability, copiesButton);
    card.append(cover, details);
    list.append(card);
  });
}

async function showBookCopies(book) {
  try {
    const copies = await api.get(`/api/books/${book.book_id}/copies`);
    const message = copies.length
      ? copies.map((copy) => `${copy.branch_name}: copy ${copy.copy_id} (${copy.status})`).join(' · ')
      : 'No physical copies are listed for this title.';
    setNotice('catalogMessage', `${book.title} — ${message}`, 'success');
    document.getElementById('catalogMessage').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  } catch (error) {
    setNotice('catalogMessage', error.message, 'error');
  }
}

function fillSelect(select, rows, getValue, getLabel, placeholder) {
  select.replaceChildren();
  const first = element('option', '', placeholder);
  first.value = '';
  select.append(first);
  rows.forEach((row) => {
    const option = element('option', '', getLabel(row));
    option.value = getValue(row);
    select.append(option);
  });
}

function showBranchCopyInputs() {
  const container = document.getElementById('branchCopies');
  container.replaceChildren(...branches.map((branch) => {
    const label = element('label', '', branch.branch_name);
    const input = element('input');
    input.type = 'number';
    input.min = '0';
    input.max = '50';
    input.value = '0';
    input.dataset.branchId = branch.branch_id;
    label.append(input);
    return label;
  }));
}

function setSessionUi() {
  const label = document.getElementById('sessionLabel');
  const logoutButton = document.getElementById('logoutButton');
  const memberGuest = document.getElementById('memberGuest');
  const memberDashboard = document.getElementById('memberDashboard');
  const librarianGuest = document.getElementById('librarianGuest');
  const librarianDashboard = document.getElementById('librarianDashboard');

  memberGuest.classList.toggle('hidden', memberIsSignedIn);
  memberDashboard.classList.toggle('hidden', !memberIsSignedIn);
  librarianGuest.classList.toggle('hidden', librarianIsSignedIn);
  librarianDashboard.classList.toggle('hidden', !librarianIsSignedIn);

  if (memberIsSignedIn && librarianIsSignedIn) label.textContent = 'Member + librarian signed in';
  else if (memberIsSignedIn) label.textContent = 'Member signed in';
  else if (librarianIsSignedIn) label.textContent = 'Librarian signed in';
  else label.textContent = 'Browsing as guest';

  logoutButton.classList.toggle('hidden', !memberIsSignedIn && !librarianIsSignedIn);
}

async function loadCatalogue() {
  try {
    [books, branches] = await Promise.all([
      api.get('/api/books'),
      api.get('/api/branches'),
    ]);
    showBranchCopyInputs();
    document.getElementById('bookCount').textContent = books.length;
    document.getElementById('branchCount').textContent = branches.length;
    document.getElementById('copyCount').textContent = books.reduce(
      (total, book) => total + Number(book.available_copies || 0),
      0,
    );
    renderBooks();
    fillSelect(
      document.getElementById('checkoutBook'),
      books,
      (book) => book.book_id,
      (book) => book.title,
      'Choose a book',
    );
  } catch (error) {
    setNotice('catalogMessage', error.message, 'error');
  }
}

async function loadCopiesForCheckout() {
  const bookId = document.getElementById('checkoutBook').value;
  const copySelect = document.getElementById('checkoutCopy');
  if (!bookId) {
    fillSelect(copySelect, [], () => '', () => '', 'Choose a book first');
    return;
  }

  try {
    const copies = await api.get(`/api/books/${bookId}/copies`);
    const available = copies.filter((copy) => copy.status === 'available');
    fillSelect(
      copySelect,
      available,
      (copy) => copy.copy_id,
      (copy) => `Copy ${copy.copy_id} · ${copy.branch_name}`,
      available.length ? 'Choose an available copy' : 'No copies available',
    );
  } catch (error) {
    setMessage('checkoutMessage', error.message, 'error');
  }
}

async function loadMemberLoans() {
  const loans = await api.get('/api/me/loans');
  document.getElementById('myLoanCount').textContent = loans.filter((loan) => !loan.returned_at).length;
  const rows = loans.map((loan) => [
    loan.title,
    formatDate(loan.issued_at),
    formatDate(loan.due_date),
    loan.returned_at ? 'Returned' : 'On loan',
  ]);
  document.getElementById('myLoans').replaceChildren(
    makeTable(['Book', 'Borrowed', 'Due date', 'Status'], rows, 'You have no loans yet.'),
  );
}

async function loadMemberFines() {
  const fines = await api.get('/api/me/fines');
  document.getElementById('myFineCount').textContent = fines.filter((fine) => !fine.is_paid).length;
  const rows = fines.map((fine) => {
    const status = element('span', fine.is_paid ? 'status-chip status-paid' : 'status-chip status-due', fine.is_paid ? 'Paid' : 'Unpaid');
    if (!fine.is_paid) {
      const payButton = element('button', 'button button-small button-secondary', 'Mark paid');
      payButton.type = 'button';
      payButton.addEventListener('click', async () => {
        payButton.disabled = true;
        try {
          await api.post(`/api/fines/${fine.fine_id}/pay`, {});
          setMessage('memberAccountMessage', 'Fine marked as paid.', 'success');
          await loadMemberFines();
        } catch (error) {
          setMessage('memberAccountMessage', error.message, 'error');
          payButton.disabled = false;
        }
      });
      status.append(document.createTextNode(' '), payButton);
    }
    return [fine.fine_id, fine.loan_id, formatCurrency(fine.fine_amount), status];
  });
  document.getElementById('myFines').replaceChildren(
    makeTable(['Fine', 'Loan', 'Amount', 'Status'], rows, 'You have no fines.'),
  );
}

async function refreshMemberArea() {
  try {
    await Promise.all([loadMemberLoans(), loadMemberFines()]);
  } catch (error) {
    setMessage('memberAccountMessage', error.message, 'error');
    if (error.message.toLowerCase().includes('token')) {
      memberIsSignedIn = false;
      sessionStorage.removeItem(memberTokenKey);
      setSessionUi();
    }
  }
}

async function loadMembers() {
  members = await api.get('/api/members');
  fillSelect(
    document.getElementById('checkoutMember'),
    members,
    (member) => member.member_id,
    (member) => `${member.member_name} · ${member.email}`,
    'Choose a member',
  );
  const rows = members.map((member) => [
    member.member_name,
    member.email,
    formatDate(member.joined_date),
  ]);
  document.getElementById('memberList').replaceChildren(
    makeTable(['Member', 'Email', 'Joined'], rows, 'No members have registered yet.'),
  );
}

async function loadAllLoans() {
  const loans = await api.get('/api/loans');
  const rows = loans.map((loan) => {
    const action = loan.returned_at
      ? element('span', 'status-chip status-paid', 'Returned')
      : element('button', 'button button-small button-secondary', 'Return');
    if (!loan.returned_at) {
      action.type = 'button';
      action.addEventListener('click', async () => {
        action.disabled = true;
        try {
          const result = await api.post(`/api/loans/${loan.loan_id}/return`, {});
          const fineText = result.fine_amount > 0
            ? `Returned. Fine: ${formatCurrency(result.fine_amount)} (${result.late_days} late days).`
            : 'Book returned. No fine due.';
          setMessage('checkoutMessage', fineText, 'success');
          await Promise.all([loadAllLoans(), loadCatalogue()]);
        } catch (error) {
          setMessage('checkoutMessage', error.message, 'error');
          action.disabled = false;
        }
      });
    }
    return [
      loan.loan_id,
      loan.member_name,
      loan.title,
      formatDate(loan.due_date),
      loan.returned_at ? formatDate(loan.returned_at) : 'Not returned',
      action,
    ];
  });
  document.getElementById('allLoans').replaceChildren(
    makeTable(['Loan', 'Member', 'Book', 'Due date', 'Returned', 'Action'], rows, 'No loans yet.'),
  );
}

async function loadOverdue() {
  const overdue = await api.get('/api/reports/overdue');
  const rows = overdue.map((loan) => [
    loan.loan_id,
    loan.member_name,
    loan.title,
    formatDate(loan.due_date),
    `${loan.late_days} days`,
  ]);
  document.getElementById('overdueList').replaceChildren(
    makeTable(['Loan', 'Member', 'Book', 'Due date', 'Late'], rows, 'No overdue loans. Great work!'),
  );
}

async function loadPopularBooks() {
  const popular = await api.get('/api/reports/most-borrowed');
  const rows = popular.map((book, index) => [
    `#${index + 1}`,
    book.title,
    book.times_borrowed,
  ]);
  document.getElementById('popularList').replaceChildren(
    makeTable(['Rank', 'Book', 'Loans'], rows, 'No borrowing activity yet.'),
  );
}

async function loadAllFines() {
  const fines = await api.get('/api/fines');
  const rows = fines.map((fine) => [
    fine.fine_id,
    fine.member_name,
    fine.loan_id,
    formatCurrency(fine.fine_amount),
    element('span', fine.is_paid ? 'status-chip status-paid' : 'status-chip status-due', fine.is_paid ? 'Paid' : 'Unpaid'),
  ]);
  document.getElementById('allFines').replaceChildren(
    makeTable(['Fine', 'Member', 'Loan', 'Amount', 'Status'], rows, 'No fines recorded.'),
  );
}

async function refreshLibrarianArea() {
  const results = await Promise.allSettled([
    loadMembers(),
    loadAllLoans(),
    loadOverdue(),
    loadPopularBooks(),
    loadAllFines(),
  ]);
  const failed = results.find((result) => result.status === 'rejected');
  if (failed) throw failed.reason;
}

document.getElementById('searchInput').addEventListener('input', renderBooks);

document.getElementById('memberLoginForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  setMessage('memberLoginMessage', 'Signing in…');
  try {
    const result = await api.post('/api/members/login', {
      email: form.elements.email.value.trim(),
      password: form.elements.password.value,
    });
    sessionStorage.setItem(memberTokenKey, result.access_token);
    memberToken = result.access_token;
    memberIsSignedIn = true;
    form.reset();
    setSessionUi();
    setMessage('memberLoginMessage', 'You are signed in.', 'success');
    await refreshMemberArea();
  } catch (error) {
    setMessage('memberLoginMessage', error.message, 'error');
  }
});

document.getElementById('registerForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  try {
    await api.post('/api/members', {
      member_name: form.elements.member_name.value.trim(),
      email: form.elements.email.value.trim(),
      password: form.elements.password.value,
    });
    form.reset();
    setMessage('registerMessage', 'Account created. You can log in now.', 'success');
  } catch (error) {
    setMessage('registerMessage', error.message, 'error');
  }
});

document.getElementById('librarianLoginForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  setMessage('librarianLoginMessage', 'Signing in…');
  try {
    await api.post('/api/librarians/login', {
      email: form.elements.email.value.trim(),
      password: form.elements.password.value,
    });
    librarianIsSignedIn = true;
    form.reset();
    setSessionUi();
    setMessage('librarianLoginMessage', 'Librarian desk is ready.', 'success');
    await refreshLibrarianArea();
  } catch (error) {
    setMessage('librarianLoginMessage', error.message, 'error');
  }
});

document.getElementById('checkoutBook').addEventListener('change', loadCopiesForCheckout);

document.getElementById('checkoutForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  try {
    const result = await api.post('/api/loans', {
      member_id: Number(form.elements.member_id.value),
      copy_id: Number(form.elements.copy_id.value),
    });
    setMessage('checkoutMessage', `Checked out. Due ${formatDate(result.due_date)}.`, 'success');
    form.reset();
    fillSelect(document.getElementById('checkoutBook'), books, (book) => book.book_id, (book) => book.title, 'Choose a book');
    fillSelect(document.getElementById('checkoutMember'), members, (member) => member.member_id, (member) => `${member.member_name} · ${member.email}`, 'Choose a member');
    await loadCopiesForCheckout();
    await Promise.all([loadAllLoans(), loadCatalogue()]);
  } catch (error) {
    setMessage('checkoutMessage', error.message, 'error');
  }
});

document.getElementById('addBookForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const year = form.elements.published_year.value;
  const authors = form.elements.author_names.value
    .split(',')
    .map((name) => name.trim())
    .filter(Boolean);
  const branchCopies = Object.fromEntries(
    [...form.querySelectorAll('[data-branch-id]')].map((input) => [
      input.dataset.branchId,
      Number(input.value),
    ]),
  );
  try {
    await api.post('/api/books', {
      title: form.elements.title.value.trim(),
      isbn: form.elements.isbn.value.trim() || null,
      published_year: year ? Number(year) : null,
      author_names: authors,
      branch_copies: branchCopies,
    });
    form.reset();
    setMessage('bookMessage', 'Book and copies added to the catalogue.', 'success');
    await loadCatalogue();
  } catch (error) {
    setMessage('bookMessage', error.message, 'error');
  }
});

document.getElementById('partnerForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const results = document.getElementById('partnerResults');
  results.replaceChildren();
  try {
    const catalog = await api.get('/api/partner/books', {
      headers: {
        'X-API-Key': form.elements.api_key.value,
        'X-API-Secret': form.elements.api_secret.value,
      },
    });
    setMessage('partnerMessage', 'Partner connection successful.', 'success');
    results.append(makeTable(
      ['Title', 'Author', 'ISBN', 'Available'],
      catalog.map((book) => [book.title, book.authors || '—', book.isbn || '—', book.available_copies]),
      'No catalogue entries.',
    ));
    form.reset();
  } catch (error) {
    setMessage('partnerMessage', error.message, 'error');
  }
});

document.querySelectorAll('.desk-tab').forEach((tab) => {
  tab.addEventListener('click', async () => {
    document.querySelectorAll('.desk-tab').forEach((item) => {
      const selected = item === tab;
      item.classList.toggle('active', selected);
      item.setAttribute('aria-selected', String(selected));
    });
    document.querySelectorAll('.desk-panel').forEach((panel) => {
      panel.classList.toggle('hidden', panel.id !== `tab-${tab.dataset.tab}`);
    });

    if (!librarianIsSignedIn) return;
    try {
      if (tab.dataset.tab === 'circulation') await Promise.all([loadMembers(), loadAllLoans()]);
      if (tab.dataset.tab === 'collection') await loadMembers();
      if (tab.dataset.tab === 'reports') {
        await Promise.all([loadOverdue(), loadPopularBooks(), loadAllFines()]);
      }
    } catch (error) {
      setMessage('checkoutMessage', error.message, 'error');
      setMessage('bookMessage', error.message, 'error');
    }
  });
});

document.getElementById('refreshMemberButton').addEventListener('click', refreshMemberArea);
document.getElementById('refreshLoansButton').addEventListener('click', () => loadAllLoans().catch((error) => setMessage('checkoutMessage', error.message, 'error')));
document.getElementById('refreshMembersButton').addEventListener('click', () => loadMembers().catch((error) => setMessage('bookMessage', error.message, 'error')));
document.getElementById('refreshOverdueButton').addEventListener('click', () => loadOverdue().catch((error) => setNotice('catalogMessage', error.message, 'error')));
document.getElementById('refreshPopularButton').addEventListener('click', () => loadPopularBooks().catch((error) => setNotice('catalogMessage', error.message, 'error')));
document.getElementById('refreshFinesButton').addEventListener('click', () => loadAllFines().catch((error) => setNotice('catalogMessage', error.message, 'error')));

document.getElementById('logoutButton').addEventListener('click', async () => {
  const errors = [];
  if (memberIsSignedIn) {
    try {
      await api.post('/api/members/logout', {});
    } catch (error) {
      errors.push(`Member logout: ${error.message}`);
    }
    sessionStorage.removeItem(memberTokenKey);
    memberToken = null;
    memberIsSignedIn = false;
  }
  if (librarianIsSignedIn) {
    try {
      await api.post('/api/librarians/logout', {});
    } catch (error) {
      errors.push(`Librarian logout: ${error.message}`);
    }
    librarianIsSignedIn = false;
  }
  setSessionUi();
  if (errors.length) setNotice('catalogMessage', errors.join(' '), 'error');
  else setNotice('catalogMessage', 'You have been logged out.', 'success');
});

async function restoreMemberSession() {
  if (!memberIsSignedIn) return;
  try {
    await refreshMemberArea();
  } catch {
    sessionStorage.removeItem(memberTokenKey);
    memberIsSignedIn = false;
  }
}

async function restoreLibrarianSession() {
  try {
    await api.get('/api/loans');
    librarianIsSignedIn = true;
    setSessionUi();
    await refreshLibrarianArea();
  } catch {
    librarianIsSignedIn = false;
  }
}

async function startDashboard() {
  setSessionUi();
  await loadCatalogue();
  await Promise.all([restoreMemberSession(), restoreLibrarianSession()]);
  setSessionUi();
}

startDashboard();
