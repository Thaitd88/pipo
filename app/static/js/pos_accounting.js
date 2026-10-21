/**
 * pos_accounting.js
 * Quản lý Sổ Quỹ Thu - Chi (Capex & Opex) cho Thu Ngân và Quản Trị Sân Pick.
 */

let accCategoriesData = null;

async function openAccountingModal(defaultDept = 'RESTAURANT') {
  const modal = document.getElementById("accountingModal");
  if (!modal) return;

  const deptEl = document.getElementById("accDepartment");
  if (deptEl && defaultDept) {
    deptEl.value = defaultDept;
  }

  modal.classList.remove("hidden");
  switchAccountingTab('form');
  await loadAccountingCategories();
  onAccTransTypeChange();
}

function closeAccountingModal() {
  const modal = document.getElementById("accountingModal");
  if (modal) modal.classList.add("hidden");
}

function switchAccountingTab(tab) {
  const formTab = document.getElementById("accTabBtn-form");
  const histTab = document.getElementById("accTabBtn-history");
  const formBox = document.getElementById("accountingForm");
  const histBox = document.getElementById("accTabContent-history");

  if (tab === 'form') {
    if (formTab) formTab.className = "px-4 py-2.5 rounded-t-xl bg-white border-t-2 border-emerald-700 text-emerald-900 shadow-xs flex items-center gap-1.5";
    if (histTab) histTab.className = "px-4 py-2.5 rounded-t-xl text-stone-500 hover:text-stone-800 flex items-center gap-1.5";
    if (formBox) formBox.classList.remove("hidden");
    if (histBox) histBox.classList.add("hidden");
  } else {
    if (formTab) formTab.className = "px-4 py-2.5 rounded-t-xl text-stone-500 hover:text-stone-800 flex items-center gap-1.5";
    if (histTab) histTab.className = "px-4 py-2.5 rounded-t-xl bg-white border-t-2 border-emerald-700 text-emerald-900 shadow-xs flex items-center gap-1.5";
    if (formBox) formBox.classList.add("hidden");
    if (histBox) histBox.classList.remove("hidden");
    loadAccountingTodaySummary();
  }
}

async function loadAccountingCategories() {
  if (accCategoriesData) return;
  try {
    const res = await fetch("/api/accounting/categories");
    if (res.ok) {
      const data = await res.json();
      accCategoriesData = data.categories;
    }
  } catch (err) {
    console.error("Lỗi tải danh mục kế toán:", err);
  }
}

function onAccTransTypeChange() {
  const transType = document.getElementById("accTransType")?.value || "EXPENSE";
  const costCatEl = document.getElementById("accCostCategory");
  const expenseTypeEl = document.getElementById("accExpenseType");
  if (!expenseTypeEl) return;

  if (transType === 'INCOME') {
    if (costCatEl) {
      costCatEl.disabled = true;
      costCatEl.classList.add("opacity-50");
    }
    const incomeCats = (accCategoriesData && accCategoriesData.INCOME) || [];
    expenseTypeEl.innerHTML = incomeCats.map(c => `
      <option value="${c.code}">${c.icon} ${c.name}</option>
    `).join('');
  } else {
    if (costCatEl) {
      costCatEl.disabled = false;
      costCatEl.classList.remove("opacity-50");
    }
    const catType = costCatEl?.value || "OPEX";
    const expCats = (accCategoriesData && accCategoriesData[catType]) || [];
    expenseTypeEl.innerHTML = expCats.map(c => `
      <option value="${c.code}">${c.icon} ${c.name}</option>
    `).join('');
  }
}

// Lắng nghe thay đổi phân loại Capex/Opex
document.addEventListener("DOMContentLoaded", () => {
  const costCatEl = document.getElementById("accCostCategory");
  if (costCatEl) {
    costCatEl.addEventListener("change", () => {
      onAccTransTypeChange();
    });
  }
});

async function submitAccountingTransaction(event) {
  event.preventDefault();

  const transType = document.getElementById("accTransType").value;
  const costCat = transType === 'EXPENSE' ? document.getElementById("accCostCategory").value : null;
  const dept = document.getElementById("accDepartment").value;
  const expType = document.getElementById("accExpenseType").value;
  const amount = parseInt(document.getElementById("accAmount").value) || 0;
  const pMethod = document.getElementById("accPaymentMethod").value;
  const recipient = (document.getElementById("accRecipientPayer")?.value || "").trim();
  const desc = (document.getElementById("accDescription")?.value || "").trim();

  if (amount <= 0) {
    alert("Vui lòng nhập số tiền hợp lệ (> 0 VNĐ)!");
    return;
  }
  if (!desc) {
    alert("Vui lòng nhập diễn giải chi tiết cho khoản thu/chi này!");
    return;
  }

  const payload = {
    transaction_type: transType,
    cost_category: costCat,
    department: dept,
    expense_type: expType,
    amount: amount,
    payment_method: pMethod,
    recipient_payer: recipient,
    description: desc
  };

  try {
    const res = await fetch("/api/accounting/transactions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Không thể tạo phiếu thu/chi");
    }

    alert(`✅ ${data.message}`);
    // Reset form
    document.getElementById("accAmount").value = "";
    document.getElementById("accDescription").value = "";
    if (document.getElementById("accRecipientPayer")) {
      document.getElementById("accRecipientPayer").value = "";
    }

    switchAccountingTab('history');
  } catch (err) {
    alert("❌ Lỗi khi lưu phiếu thu chi: " + err.message);
  }
}

async function loadAccountingTodaySummary() {
  try {
    const res = await fetch("/api/accounting/summary-today");
    if (!res.ok) return;
    const data = await res.json();

    if (document.getElementById("accKpiPos")) document.getElementById("accKpiPos").innerText = (data.pos_revenue || 0).toLocaleString() + " đ";
    if (document.getElementById("accKpiOpex")) document.getElementById("accKpiOpex").innerText = (data.opex_spent || 0).toLocaleString() + " đ";
    if (document.getElementById("accKpiCapex")) document.getElementById("accKpiCapex").innerText = (data.capex_spent || 0).toLocaleString() + " đ";
    if (document.getElementById("accKpiDrawer")) document.getElementById("accKpiDrawer").innerText = (data.cash_in_drawer_estimate || 0).toLocaleString() + " đ";

    // Danh sách phiếu hôm nay
    const txRes = await fetch("/api/accounting/transactions?from_date=" + new Date().toISOString().split('T')[0]);
    if (txRes.ok) {
      const txData = await txRes.json();
      renderAccountingTodayList(txData.transactions || []);
    }
  } catch (err) {
    console.error("Lỗi loadAccountingTodaySummary:", err);
  }
}

function renderAccountingTodayList(txs) {
  const tbody = document.getElementById("accTransactionsTableBody") || document.getElementById("accTodayTxTableBody");
  if (!tbody) return;

  if (txs.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" class="text-center py-6 text-stone-400 text-xs">Hôm nay chưa có phiếu thu/chi nào phát sinh</td></tr>`;
    return;
  }

  tbody.innerHTML = txs.map(t => {
    const isIncome = t.transaction_type === 'INCOME';
    const amountClass = isIncome ? 'text-emerald-700 font-bold' : 'text-rose-600 font-bold';
    const prefix = isIncome ? '+' : '-';

    return `
      <tr class="hover:bg-stone-50 transition border-b border-stone-100 text-xs">
        <td class="px-3 py-2 font-mono font-bold text-stone-800">${t.code}</td>
        <td class="px-3 py-2 text-stone-500 whitespace-nowrap">${t.transaction_date}</td>
        <td class="px-3 py-2">
          <span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${isIncome ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-900'}">
            ${isIncome ? '💰 THU' : (t.cost_category || 'CHI')}
          </span>
          <span class="text-[10px] text-stone-500 ml-1">(${t.department})</span>
        </td>
        <td class="px-3 py-2">
          <div class="font-medium text-stone-800">${t.description}</div>
          ${t.recipient_payer ? `<div class="text-[10px] text-stone-400">Người nhận/nộp: ${t.recipient_payer}</div>` : ''}
        </td>
        <td class="px-3 py-2 text-right ${amountClass}">
          ${prefix}${t.amount.toLocaleString()} đ
        </td>
        <td class="px-3 py-2 text-center text-stone-400">
          <button onclick="deleteAccTx(${t.id})" class="text-rose-500 hover:text-rose-700 text-xs" title="Xóa phiếu">
            <i class="fa-solid fa-trash"></i>
          </button>
        </td>
      </tr>
    `;
  }).join('');
}

async function deleteAccTx(txId) {
  if (!confirm("Bạn có chắc chắn muốn xóa phiếu thu/chi này không?")) return;
  try {
    const res = await fetch(`/api/accounting/transactions/${txId}`, { method: "DELETE" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Không thể xóa");
    alert("Đã xóa phiếu thành công!");
    loadAccountingTodaySummary();
  } catch (err) {
    alert("Lỗi khi xóa: " + err.message);
  }
}
