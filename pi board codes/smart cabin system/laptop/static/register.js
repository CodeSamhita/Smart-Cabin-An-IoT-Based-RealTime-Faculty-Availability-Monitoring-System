// Smart Cabin - admin: register faculty, edit them, open their timetable.

let faculty = [];
let editingId = null;          // null = adding a new person

const FIELDS = ["name", "position", "designation", "school", "department", "email", "username", "password"];

function formData() {
  const data = {};
  FIELDS.forEach(f => data[f] = $("f-" + f).value.trim());
  data.active = editingId === null ? true : $("f-active").checked;
  return data;
}

function clearForm() {
  editingId = null;
  FIELDS.forEach(f => $("f-" + f).value = f === "position" ? "Faculty" : "");
  $("form-title").textContent = "New faculty member";
  $("save").textContent = "Register";
  $("password-label").textContent = "Password";
  $("cancel").classList.add("hidden");
  $("active-row").classList.add("hidden");
  $("form-error").textContent = "";
}

function edit(id) {
  const p = faculty.find(x => x.id === id);
  editingId = id;
  FIELDS.forEach(f => $("f-" + f).value = f === "password" ? "" : (p[f] || ""));
  $("f-active").checked = !!p.active;
  $("form-title").textContent = "Edit " + p.name;
  $("save").textContent = "Save changes";
  $("password-label").textContent = "New password (empty = keep)";
  $("cancel").classList.remove("hidden");
  $("active-row").classList.remove("hidden");
  document.querySelector(".panels").scrollTo({ left: 0, behavior: "smooth" });   // back to the form on a phone
  window.scrollTo({ top: 0, behavior: "smooth" });
}

async function save() {
  $("form-error").textContent = "";
  try {
    if (editingId === null) {
      await api("POST", "/api/admin/faculty", formData());
      toast("Registered " + $("f-name").value + ". Give them the username and password.");
    } else {
      await api("PUT", "/api/admin/faculty/" + editingId, formData());
      toast("Saved.");
    }
    clearForm();
    load();
  } catch (e) {
    $("form-error").textContent = e.message;
  }
}

function row(p) {
  const devices = [p.cabin ? "Cabin " + p.cabin : "no cabin", p.cards + " card" + (p.cards === 1 ? "" : "s"),
                   p.phones + " phone" + (p.phones === 1 ? "" : "s"), p.face_photos ? "face ✔" : "no face"];
  return "<div class='list-row'><div><b>" + esc(p.name) + "</b>" + (p.active ? "" : " <span class='tag'>blocked</span>") +
    "<div class='small'>" + esc([p.position, p.designation, p.department].filter(Boolean).join(" · ")) + "</div>" +
    "<div class='mono'>" + esc(p.username) + " · " + esc(devices.join(" · ")) + "</div></div>" +
    "<div style='flex:none'><button class='plain small-btn' onclick='edit(" + p.id + ")'>Edit</button> " +
    "<a href='/timetable?person=" + p.id + "'><button class='plain small-btn'>Timetable</button></a></div></div>";
}

function showList() {
  const words = $("find").value.toLowerCase().split(/\s+/).filter(Boolean);
  const shown = faculty.filter(p => {
    const text = [p.name, p.username, p.position, p.designation, p.school, p.department, p.cabin].join(" ").toLowerCase();
    return words.every(w => text.includes(w));
  });
  $("count").textContent = faculty.length;
  $("list").innerHTML = shown.length ? shown.map(row).join("")
    : "<p class='small'>" + (faculty.length ? "Nobody matches." : "Nobody registered yet. Use the form.") + "</p>";
}

async function load() {
  const data = await api("GET", "/api/admin/faculty");
  faculty = data.faculty;
  // Suggestions for school and department, from what was typed before
  const unique = list => [...new Set(list.filter(Boolean))].sort();
  $("schools").innerHTML = unique(faculty.map(p => p.school)).map(s => "<option value='" + esc(s) + "'>").join("");
  $("departments").innerHTML = unique(faculty.map(p => p.department)).map(s => "<option value='" + esc(s) + "'>").join("");
  showList();
}

async function importAiSchool() {
  if (!confirm("Add the AI School faculty from the website list? People already registered are skipped.")) return;
  const response = await fetch("/api/admin/import-ai-school", { method: "POST" });
  if (!response.ok) { $("import-msg").textContent = (await response.json()).detail; return; }
  const added = Number(response.headers.get("X-Added"));
  if (added > 0) {
    // The passwords can only be seen now: save them as a file to hand out
    const link = document.createElement("a");
    link.href = URL.createObjectURL(await response.blob());
    link.download = "ai_school_logins.csv";
    link.click();
  }
  $("import-msg").textContent = added ? added + " added. Their usernames and temporary passwords were downloaded " +
    "(ai_school_logins.csv). Keep that file safe: the passwords can't be shown again." : "Nobody new to add.";
  load();
}

$("import").onclick = importAiSchool;
$("save").onclick = save;
$("cancel").onclick = clearForm;
$("find").addEventListener("input", showList);
load();
