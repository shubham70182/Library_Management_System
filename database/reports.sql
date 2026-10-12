-- Loans that are overdue and have not been returned.
SELECT l.loan_id, m.member_name, b.title, l.due_date,
       CAST(julianday(CURRENT_DATE) - julianday(l.due_date) AS INTEGER) AS late_days
FROM loans l
JOIN members m ON m.member_id = l.member_id
JOIN book_copies c ON c.copy_id = l.copy_id
JOIN books b ON b.book_id = c.book_id
WHERE l.returned_at IS NULL
  AND l.due_date < CURRENT_DATE
ORDER BY l.due_date;

-- Books that are currently issued to members.
SELECT l.loan_id, m.member_name, b.title, l.issued_at, l.due_date
FROM loans l
JOIN members m ON m.member_id = l.member_id
JOIN book_copies c ON c.copy_id = l.copy_id
JOIN books b ON b.book_id = c.book_id
WHERE l.returned_at IS NULL
ORDER BY l.due_date;

-- Books with the largest number of loans.
SELECT b.book_id, b.title, COUNT(l.loan_id) AS times_borrowed
FROM books b
JOIN book_copies c ON c.book_id = b.book_id
JOIN loans l ON l.copy_id = c.copy_id
GROUP BY b.book_id, b.title
ORDER BY times_borrowed DESC;

-- Total number of books borrowed by each member.
SELECT m.member_id, m.member_name, COUNT(l.loan_id) AS books_borrowed
FROM members m
LEFT JOIN loans l ON l.member_id = m.member_id
GROUP BY m.member_id, m.member_name
ORDER BY m.member_name;

-- Number of available copies at each branch.
SELECT br.branch_name, b.title, COUNT(c.copy_id) AS available_copies
FROM branches br
JOIN book_copies c ON c.branch_id = br.branch_id
JOIN books b ON b.book_id = c.book_id
WHERE c.status = 'available'
GROUP BY br.branch_id, br.branch_name, b.book_id, b.title
ORDER BY br.branch_name, b.title;

-- Fines that members have not paid yet.
SELECT m.member_name, f.fine_id, f.fine_amount
FROM fines f
JOIN loans l ON l.loan_id = f.loan_id
JOIN members m ON m.member_id = l.member_id
WHERE f.is_paid = FALSE
ORDER BY m.member_name;
