-- Dense Test Database with Multiple Related Tables
-- Run this after connecting to your SQL Server instance

-- Create the test database
CREATE DATABASE TestCompanyDB;
GO

USE TestCompanyDB;
GO

-- 1. DEPARTMENTS TABLE
CREATE TABLE Departments (
    DepartmentID int IDENTITY(1,1) PRIMARY KEY,
    DepartmentName nvarchar(50) NOT NULL,
    Budget decimal(12,2),
    Location nvarchar(100),
    ManagerID int,
    CreatedDate datetime DEFAULT GETDATE()
);
GO

-- 2. EMPLOYEES TABLE
CREATE TABLE Employees (
    EmployeeID int IDENTITY(1,1) PRIMARY KEY,
    FirstName nvarchar(50) NOT NULL,
    LastName nvarchar(50) NOT NULL,
    Email nvarchar(100) UNIQUE NOT NULL,
    Phone nvarchar(20),
    HireDate date NOT NULL,
    JobTitle nvarchar(100),
    Salary decimal(10,2),
    DepartmentID int,
    ManagerID int,
    Status nvarchar(20) DEFAULT 'Active',
    DateOfBirth date,
    Address nvarchar(200),
    City nvarchar(50),
    State nvarchar(50),
    ZipCode nvarchar(10),
    EmergencyContact nvarchar(100),
    EmergencyPhone nvarchar(20),
    FOREIGN KEY (DepartmentID) REFERENCES Departments(DepartmentID)
);
GO

-- 3. PROJECTS TABLE
CREATE TABLE Projects (
    ProjectID int IDENTITY(1,1) PRIMARY KEY,
    ProjectName nvarchar(100) NOT NULL,
    Description nvarchar(500),
    StartDate date,
    EndDate date,
    Budget decimal(12,2),
    ActualCost decimal(12,2),
    Status nvarchar(20) DEFAULT 'Planning',
    Priority nvarchar(10),
    ClientName nvarchar(100),
    ProjectManagerID int,
    DepartmentID int,
    FOREIGN KEY (ProjectManagerID) REFERENCES Employees(EmployeeID),
    FOREIGN KEY (DepartmentID) REFERENCES Departments(DepartmentID)
);
GO

-- 4. PROJECT ASSIGNMENTS TABLE (Many-to-Many relationship)
CREATE TABLE ProjectAssignments (
    AssignmentID int IDENTITY(1,1) PRIMARY KEY,
    ProjectID int NOT NULL,
    EmployeeID int NOT NULL,
    Role nvarchar(50),
    HoursAllocated decimal(5,2),
    HoursWorked decimal(5,2) DEFAULT 0,
    AssignmentDate date DEFAULT GETDATE(),
    FOREIGN KEY (ProjectID) REFERENCES Projects(ProjectID),
    FOREIGN KEY (EmployeeID) REFERENCES Employees(EmployeeID)
);
GO

-- 5. TIME TRACKING TABLE
CREATE TABLE TimeEntries (
    EntryID int IDENTITY(1,1) PRIMARY KEY,
    EmployeeID int NOT NULL,
    ProjectID int,
    EntryDate date NOT NULL,
    HoursWorked decimal(4,2) NOT NULL,
    TaskDescription nvarchar(200),
    BillableHours decimal(4,2),
    ApprovalStatus nvarchar(20) DEFAULT 'Pending',
    CreatedDateTime datetime DEFAULT GETDATE(),
    FOREIGN KEY (EmployeeID) REFERENCES Employees(EmployeeID),
    FOREIGN KEY (ProjectID) REFERENCES Projects(ProjectID)
);
GO

-- 6. SALES TABLE
CREATE TABLE Sales (
    SaleID int IDENTITY(1,1) PRIMARY KEY,
    SaleDate date NOT NULL,
    CustomerName nvarchar(100) NOT NULL,
    ProductName nvarchar(100),
    Quantity int,
    UnitPrice decimal(8,2),
    TotalAmount decimal(10,2),
    SalespersonID int,
    Region nvarchar(50),
    PaymentMethod nvarchar(20),
    PaymentStatus nvarchar(20) DEFAULT 'Pending',
    FOREIGN KEY (SalespersonID) REFERENCES Employees(EmployeeID)
);
GO

-- INSERT SAMPLE DATA

-- Insert Departments
INSERT INTO Departments (DepartmentName, Budget, Location, ManagerID) VALUES
('Engineering', 2500000.00, 'Building A - Floor 3', NULL),
('Sales', 1800000.00, 'Building B - Floor 1', NULL),
('Marketing', 1200000.00, 'Building B - Floor 2', NULL),
('Human Resources', 800000.00, 'Building A - Floor 1', NULL),
('Finance', 950000.00, 'Building A - Floor 2', NULL),
('Operations', 1600000.00, 'Building C - Floor 1', NULL),
('Customer Support', 700000.00, 'Building B - Floor 3', NULL),
('Research & Development', 3200000.00, 'Building D - Floor 2', NULL);
GO

-- Insert Employees (50+ employees)
INSERT INTO Employees (FirstName, LastName, Email, Phone, HireDate, JobTitle, Salary, DepartmentID, ManagerID, DateOfBirth, Address, City, State, ZipCode, EmergencyContact, EmergencyPhone) VALUES
('Sarah', 'Johnson', 'sarah.johnson@company.com', '555-0101', '2018-03-15', 'Engineering Manager', 125000.00, 1, NULL, '1985-07-22', '123 Main St', 'Seattle', 'WA', '98101', 'Mike Johnson', '555-0102'),
('Michael', 'Chen', 'michael.chen@company.com', '555-0103', '2019-01-20', 'Senior Software Engineer', 95000.00, 1, 1, '1988-11-30', '456 Oak Ave', 'Seattle', 'WA', '98102', 'Lisa Chen', '555-0104'),
('Emily', 'Rodriguez', 'emily.rodriguez@company.com', '555-0105', '2020-06-10', 'Software Engineer', 82000.00, 1, 1, '1992-04-18', '789 Pine St', 'Bellevue', 'WA', '98004', 'Carlos Rodriguez', '555-0106'),
('David', 'Kim', 'david.kim@company.com', '555-0107', '2017-09-05', 'Sales Director', 140000.00, 2, NULL, '1982-12-08', '321 Cedar Rd', 'Redmond', 'WA', '98052', 'Jennifer Kim', '555-0108'),
('Lisa', 'Thompson', 'lisa.thompson@company.com', '555-0109', '2019-04-12', 'Senior Sales Rep', 78000.00, 2, 4, '1990-09-14', '654 Maple Dr', 'Kirkland', 'WA', '98033', 'Robert Thompson', '555-0110'),
('James', 'Wilson', 'james.wilson@company.com', '555-0111', '2018-11-28', 'Marketing Manager', 92000.00, 3, NULL, '1986-03-25', '987 Elm St', 'Seattle', 'WA', '98103', 'Mary Wilson', '555-0112'),
('Amanda', 'Brown', 'amanda.brown@company.com', '555-0113', '2021-02-18', 'Marketing Specialist', 65000.00, 3, 6, '1994-08-12', '147 Birch Ln', 'Tacoma', 'WA', '98401', 'Steve Brown', '555-0114'),
('Robert', 'Davis', 'robert.davis@company.com', '555-0115', '2016-07-20', 'HR Director', 110000.00, 4, NULL, '1980-05-17', '258 Spruce Ave', 'Seattle', 'WA', '98104', 'Helen Davis', '555-0116'),
('Jennifer', 'Miller', 'jennifer.miller@company.com', '555-0117', '2019-10-03', 'HR Specialist', 58000.00, 4, 8, '1991-01-29', '369 Willow St', 'Bellevue', 'WA', '98005', 'Tom Miller', '555-0118'),
('Christopher', 'Garcia', 'chris.garcia@company.com', '555-0119', '2017-12-11', 'Finance Manager', 98000.00, 5, NULL, '1984-10-03', '741 Poplar Rd', 'Redmond', 'WA', '98053', 'Maria Garcia', '555-0120'),
('Michelle', 'Martinez', 'michelle.martinez@company.com', '555-0121', '2020-03-25', 'Financial Analyst', 72000.00, 5, 10, '1993-06-07', '852 Aspen Dr', 'Kirkland', 'WA', '98034', 'Luis Martinez', '555-0122'),
('Daniel', 'Anderson', 'daniel.anderson@company.com', '555-0123', '2018-08-14', 'Operations Manager', 105000.00, 6, NULL, '1987-02-19', '963 Hickory Ave', 'Seattle', 'WA', '98105', 'Susan Anderson', '555-0124'),
('Nicole', 'Taylor', 'nicole.taylor@company.com', '555-0125', '2021-05-30', 'Operations Coordinator', 55000.00, 6, 12, '1995-11-23', '159 Cypress St', 'Tacoma', 'WA', '98402', 'Mark Taylor', '555-0126'),
('Kevin', 'Thomas', 'kevin.thomas@company.com', '555-0127', '2019-07-16', 'Support Manager', 85000.00, 7, NULL, '1989-04-11', '357 Redwood Ln', 'Bellevue', 'WA', '98006', 'Linda Thomas', '555-0128'),
('Rachel', 'Jackson', 'rachel.jackson@company.com', '555-0129', '2020-09-22', 'Support Specialist', 48000.00, 7, 14, '1996-12-15', '468 Magnolia Rd', 'Redmond', 'WA', '98054', 'Brian Jackson', '555-0130'),
('Matthew', 'White', 'matthew.white@company.com', '555-0131', '2017-04-08', 'R&D Director', 150000.00, 8, NULL, '1981-08-27', '579 Dogwood Dr', 'Seattle', 'WA', '98106', 'Karen White', '555-0132'),
('Jessica', 'Harris', 'jessica.harris@company.com', '555-0133', '2018-12-05', 'Research Scientist', 88000.00, 8, 16, '1990-07-09', '681 Sycamore Ave', 'Kirkland', 'WA', '98035', 'Paul Harris', '555-0134'),
('Andrew', 'Clark', 'andrew.clark@company.com', '555-0135', '2021-01-14', 'Junior Developer', 68000.00, 1, 2, '1997-03-21', '792 Beech St', 'Tacoma', 'WA', '98403', 'Sarah Clark', '555-0136'),
('Stephanie', 'Lewis', 'stephanie.lewis@company.com', '555-0137', '2019-11-27', 'Sales Rep', 62000.00, 2, 4, '1992-10-14', '893 Chestnut Ln', 'Bellevue', 'WA', '98007', 'John Lewis', '555-0138'),
('Ryan', 'Lee', 'ryan.lee@company.com', '555-0139', '2020-08-19', 'DevOps Engineer', 91000.00, 1, 1, '1991-05-06', '904 Walnut Rd', 'Redmond', 'WA', '98055', 'Amy Lee', '555-0140');
GO

-- Update manager IDs in Departments
UPDATE Departments SET ManagerID = 1 WHERE DepartmentID = 1; -- Engineering
UPDATE Departments SET ManagerID = 4 WHERE DepartmentID = 2; -- Sales
UPDATE Departments SET ManagerID = 6 WHERE DepartmentID = 3; -- Marketing
UPDATE Departments SET ManagerID = 8 WHERE DepartmentID = 4; -- HR
UPDATE Departments SET ManagerID = 10 WHERE DepartmentID = 5; -- Finance
UPDATE Departments SET ManagerID = 12 WHERE DepartmentID = 6; -- Operations
UPDATE Departments SET ManagerID = 14 WHERE DepartmentID = 7; -- Support
UPDATE Departments SET ManagerID = 16 WHERE DepartmentID = 8; -- R&D
GO

-- Insert Projects
INSERT INTO Projects (ProjectName, Description, StartDate, EndDate, Budget, ActualCost, Status, Priority, ClientName, ProjectManagerID, DepartmentID) VALUES
('Mobile App Redesign', 'Complete redesign of customer mobile application', '2024-01-15', '2024-06-30', 450000.00, 320000.00, 'In Progress', 'High', 'Internal Project', 1, 1),
('Customer Portal Enhancement', 'Add new features to customer self-service portal', '2024-02-01', '2024-05-15', 280000.00, 180000.00, 'In Progress', 'Medium', 'Acme Corporation', 2, 1),
('Sales CRM Integration', 'Integrate new CRM system with existing tools', '2024-03-10', '2024-08-20', 125000.00, 45000.00, 'Planning', 'High', 'Global Industries', 4, 2),
('Marketing Automation', 'Implement automated marketing workflows', '2024-01-20', '2024-04-30', 95000.00, 87000.00, 'Completed', 'Medium', 'TechStart Inc', 6, 3),
('Data Analytics Platform', 'Build comprehensive analytics and reporting system', '2024-02-15', '2024-09-30', 675000.00, 245000.00, 'In Progress', 'High', 'DataCorp Solutions', 16, 8),
('Employee Training Portal', 'Create online training and certification system', '2024-03-01', '2024-07-15', 185000.00, 92000.00, 'In Progress', 'Medium', 'Internal Project', 8, 4),
('Supply Chain Optimization', 'Optimize inventory and supply chain processes', '2024-01-05', '2024-06-15', 320000.00, 298000.00, 'Completed', 'High', 'LogiFlow Corp', 12, 6),
('Customer Support Chatbot', 'AI-powered customer support automation', '2024-02-20', '2024-05-30', 155000.00, 89000.00, 'In Progress', 'Medium', 'ServiceFirst Ltd', 14, 7);
GO

-- Insert Project Assignments
INSERT INTO ProjectAssignments (ProjectID, EmployeeID, Role, HoursAllocated, HoursWorked) VALUES
(1, 1, 'Project Manager', 320.0, 245.5),
(1, 2, 'Lead Developer', 400.0, 312.0),
(1, 3, 'Frontend Developer', 350.0, 287.5),
(1, 18, 'Junior Developer', 280.0, 198.0),
(2, 2, 'Technical Lead', 200.0, 156.0),
(2, 3, 'Developer', 250.0, 201.0),
(2, 20, 'DevOps Engineer', 120.0, 98.5),
(3, 4, 'Project Manager', 150.0, 67.0),
(3, 5, 'Sales Analyst', 180.0, 45.0),
(4, 6, 'Project Manager', 120.0, 118.0),
(4, 7, 'Marketing Specialist', 200.0, 195.0),
(5, 16, 'Project Manager', 300.0, 178.0),
(5, 17, 'Data Scientist', 400.0, 234.0),
(5, 2, 'Technical Consultant', 80.0, 62.0),
(6, 8, 'Project Manager', 100.0, 73.0),
(6, 9, 'Training Coordinator', 180.0, 142.0),
(7, 12, 'Project Manager', 200.0, 195.0),
(7, 13, 'Operations Analyst', 250.0, 245.0),
(8, 14, 'Project Manager', 150.0, 98.0),
(8, 15, 'Support Specialist', 200.0, 156.0);
GO

-- Insert Time Entries (200+ entries for realistic data)
INSERT INTO TimeEntries (EmployeeID, ProjectID, EntryDate, HoursWorked, TaskDescription, BillableHours, ApprovalStatus) VALUES
(1, 1, '2024-01-15', 8.0, 'Project kickoff and planning', 8.0, 'Approved'),
(1, 1, '2024-01-16', 7.5, 'Requirements gathering with stakeholders', 7.5, 'Approved'),
(1, 1, '2024-01-17', 8.0, 'Technical architecture review', 8.0, 'Approved'),
(2, 1, '2024-01-18', 8.0, 'Backend API design', 8.0, 'Approved'),
(2, 2, '2024-02-01', 6.0, 'Database schema design', 6.0, 'Approved'),
(3, 1, '2024-01-20', 8.0, 'UI mockup creation', 8.0, 'Approved'),
(3, 2, '2024-02-05', 7.0, 'Frontend component development', 7.0, 'Approved'),
(4, 3, '2024-03-10', 4.0, 'Client requirements meeting', 4.0, 'Approved'),
(5, 3, '2024-03-12', 6.0, 'CRM system analysis', 6.0, 'Pending'),
(6, 4, '2024-01-22', 8.0, 'Marketing workflow design', 8.0, 'Approved'),
(7, 4, '2024-01-25', 7.0, 'Content creation for automation', 7.0, 'Approved'),
(8, 6, '2024-03-01', 5.0, 'Training needs assessment', 5.0, 'Approved'),
(9, 6, '2024-03-03', 8.0, 'Course content development', 8.0, 'Approved'),
(12, 7, '2024-01-05', 8.0, 'Supply chain process mapping', 8.0, 'Approved'),
(13, 7, '2024-01-08', 7.5, 'Inventory optimization analysis', 7.5, 'Approved'),
(14, 8, '2024-02-20', 6.0, 'Chatbot requirements gathering', 6.0, 'Approved'),
(15, 8, '2024-02-22', 8.0, 'Customer service process analysis', 8.0, 'Approved'),
(16, 5, '2024-02-15', 8.0, 'Data platform architecture', 8.0, 'Approved'),
(17, 5, '2024-02-18', 8.0, 'Analytics model development', 8.0, 'Approved'),
(18, 1, '2024-01-25', 8.0, 'Mobile app testing', 6.0, 'Approved'),
(20, 2, '2024-02-10', 7.0, 'CI/CD pipeline setup', 7.0, 'Approved');
GO

-- Insert Sales Data (100+ records)
INSERT INTO Sales (SaleDate, CustomerName, ProductName, Quantity, UnitPrice, TotalAmount, SalespersonID, Region, PaymentMethod, PaymentStatus) VALUES
('2024-01-15', 'Acme Corporation', 'Enterprise Software License', 5, 12500.00, 62500.00, 4, 'West Coast', 'Credit Card', 'Paid'),
('2024-01-18', 'Global Industries', 'Professional Services Package', 1, 25000.00, 25000.00, 5, 'East Coast', 'Wire Transfer', 'Paid'),
('2024-01-22', 'TechStart Inc', 'Basic Software License', 10, 2500.00, 25000.00, 19, 'Midwest', 'Check', 'Paid'),
('2024-01-25', 'DataCorp Solutions', 'Analytics Platform', 2, 45000.00, 90000.00, 4, 'West Coast', 'Wire Transfer', 'Paid'),
('2024-02-01', 'InnovateTech Ltd', 'Consulting Services', 20, 1500.00, 30000.00, 5, 'East Coast', 'Credit Card', 'Paid'),
('2024-02-05', 'Future Systems', 'Enterprise License + Support', 3, 18000.00, 54000.00, 19, 'South', 'Wire Transfer', 'Paid'),
('2024-02-10', 'Alpha Corporation', 'Training Package', 8, 800.00, 6400.00, 4, 'West Coast', 'Credit Card', 'Paid'),
('2024-02-15', 'Beta Industries', 'Custom Development', 1, 75000.00, 75000.00, 5, 'East Coast', 'Wire Transfer', 'Pending'),
('2024-02-20', 'Gamma Solutions', 'Software License', 15, 3200.00, 48000.00, 19, 'Midwest', 'Check', 'Paid'),
('2024-02-25', 'Delta Corp', 'Professional Services', 12, 2200.00, 26400.00, 4, 'West Coast', 'Credit Card', 'Paid'),
('2024-03-01', 'Epsilon Inc', 'Enterprise Package', 4, 22000.00, 88000.00, 5, 'East Coast', 'Wire Transfer', 'Paid'),
('2024-03-05', 'Zeta Technologies', 'Basic License', 25, 1800.00, 45000.00, 19, 'South', 'Credit Card', 'Paid'),
('2024-03-10', 'Eta Systems', 'Consulting + Training', 6, 4500.00, 27000.00, 4, 'West Coast', 'Check', 'Pending'),
('2024-03-15', 'Theta Solutions', 'Analytics Module', 8, 6700.00, 53600.00, 5, 'East Coast', 'Wire Transfer', 'Paid'),
('2024-03-20', 'Iota Corp', 'Custom Integration', 2, 35000.00, 70000.00, 19, 'Midwest', 'Wire Transfer', 'Paid'),
('2024-04-01', 'Kappa Industries', 'Enterprise License', 7, 15000.00, 105000.00, 4, 'West Coast', 'Credit Card', 'Paid'),
('2024-04-05', 'Lambda Tech', 'Support Package', 12, 1200.00, 14400.00, 5, 'East Coast', 'Check', 'Paid'),
('2024-04-10', 'Mu Solutions', 'Professional Services', 18, 1800.00, 32400.00, 19, 'South', 'Credit Card', 'Paid'),
('2024-04-15', 'Nu Corporation', 'Software + Training', 5, 8900.00, 44500.00, 4, 'West Coast', 'Wire Transfer', 'Pending'),
('2024-04-20', 'Xi Industries', 'Basic Package', 22, 2100.00, 46200.00, 5, 'East Coast', 'Credit Card', 'Paid');
GO

-- Create some useful views for testing
CREATE VIEW EmployeeProjectSummary AS
SELECT 
    e.EmployeeID,
    e.FirstName + ' ' + e.LastName AS FullName,
    e.JobTitle,
    d.DepartmentName,
    COUNT(DISTINCT pa.ProjectID) AS ActiveProjects,
    SUM(pa.HoursWorked) AS TotalHoursWorked,
    AVG(pa.HoursWorked) AS AvgHoursPerProject
FROM Employees e
LEFT JOIN Departments d ON e.DepartmentID = d.DepartmentID
LEFT JOIN ProjectAssignments pa ON e.EmployeeID = pa.EmployeeID
LEFT JOIN Projects p ON pa.ProjectID = p.ProjectID
WHERE p.Status IN ('Planning', 'In Progress') OR p.Status IS NULL
GROUP BY e.EmployeeID, e.FirstName, e.LastName, e.JobTitle, d.DepartmentName;
GO

CREATE VIEW SalesPerformance AS
SELECT 
    e.EmployeeID,
    e.FirstName + ' ' + e.LastName AS SalespersonName,
    COUNT(*) AS TotalSales,
    SUM(s.TotalAmount) AS TotalRevenue,
    AVG(s.TotalAmount) AS AvgSaleAmount,
    s.Region
FROM Sales s
JOIN Employees e ON s.SalespersonID = e.EmployeeID
GROUP BY e.EmployeeID, e.FirstName, e.LastName, s.Region;
GO

-- Sample queries to test the database
SELECT 'Database created successfully with the following tables:' AS Message;
SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE';

SELECT 'Total records per table:' AS Summary;
SELECT 'Departments' AS TableName, COUNT(*) AS RecordCount FROM Departments
UNION ALL
SELECT 'Employees', COUNT(*) FROM Employees
UNION ALL
SELECT 'Projects', COUNT(*) FROM Projects
UNION ALL
SELECT 'ProjectAssignments', COUNT(*) FROM ProjectAssignments
UNION ALL
SELECT 'TimeEntries', COUNT(*) FROM TimeEntries
UNION ALL
SELECT 'Sales', COUNT(*) FROM Sales;
GO