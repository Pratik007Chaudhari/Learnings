
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS department (
  department_id INTEGER PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  cost_center TEXT,
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS office (
  office_id INTEGER PRIMARY KEY,
  city TEXT,
  country TEXT,
  timezone TEXT
);

CREATE TABLE IF NOT EXISTS title (
  title_id INTEGER PRIMARY KEY,
  name TEXT,
  job_family TEXT,
  level TEXT
);

CREATE TABLE IF NOT EXISTS employee (
  employee_id INTEGER PRIMARY KEY,
  first_name TEXT,
  last_name TEXT,
  email TEXT UNIQUE,
  phone TEXT,
  gender TEXT,
  birth_date TEXT,
  hire_date TEXT,
  status TEXT,
  employment_type TEXT,
  department_id INTEGER,
  office_id INTEGER,
  title_id INTEGER,
  manager_id INTEGER NULL,
  FOREIGN KEY (department_id) REFERENCES department(department_id),
  FOREIGN KEY (office_id) REFERENCES office(office_id),
  FOREIGN KEY (title_id) REFERENCES title(title_id),
  FOREIGN KEY (manager_id) REFERENCES employee(employee_id)
);

CREATE INDEX IF NOT EXISTS idx_emp_dept ON employee(department_id);
CREATE INDEX IF NOT EXISTS idx_emp_office ON employee(office_id);
CREATE INDEX IF NOT EXISTS idx_emp_manager ON employee(manager_id);

CREATE TABLE IF NOT EXISTS salary_history (
  salary_id INTEGER PRIMARY KEY,
  employee_id INTEGER NOT NULL,
  effective_date TEXT NOT NULL,
  end_date TEXT,
  currency TEXT,
  base_salary REAL,
  bonus_pct REAL,
  reason TEXT,
  FOREIGN KEY (employee_id) REFERENCES employee(employee_id)
);

CREATE INDEX IF NOT EXISTS idx_sal_emp_eff ON salary_history(employee_id, effective_date DESC);

CREATE TABLE IF NOT EXISTS project (
  project_id INTEGER PRIMARY KEY,
  code TEXT UNIQUE NOT NULL,
  name TEXT,
  department_id INTEGER,
  start_date TEXT,
  end_date TEXT,
  FOREIGN KEY (department_id) REFERENCES department(department_id)
);

CREATE INDEX IF NOT EXISTS idx_proj_dept ON project(department_id);

CREATE TABLE IF NOT EXISTS employee_project (
  employee_id INTEGER NOT NULL,
  project_id INTEGER NOT NULL,
  assigned_date TEXT,
  allocation_pct INTEGER CHECK (allocation_pct >= 5 AND allocation_pct <= 100),
  PRIMARY KEY (employee_id, project_id),
  FOREIGN KEY (employee_id) REFERENCES employee(employee_id),
  FOREIGN KEY (project_id) REFERENCES project(project_id)
);

CREATE INDEX IF NOT EXISTS idx_emp_proj_proj ON employee_project(project_id, employee_id);
