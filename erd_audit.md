# 📐 FastDrop: Final ERD Technical Specification (Source of Truth)

This document contains the complete structural definition of the FastDrop database. It covers all 16 core entities from the functional requirements plus the advanced AI intelligence layer.

---

## 1. Entity & Attribute Dictionary

### (Administrative)

1. **Role** (Req 1.1)
   * **PK:** `Role_ID`
   * **Attributes:** `Role_Name` (Unique), `Permissions_Description` (Short Text).
2. **Employee** (Req 1.2)
   * **PK:** `Employee_ID`
   * **Attributes:** `Name`, `Email` (Unique), `Phone`, `Password` (Hashed), `Account_Status` (Enum: Active, Deactivated), **`Role_ID` (FK)**, **`Manager_ID` (FK - Unary)**.
3. **Merchant** (Req 2.1)
   * **PK:** `Merchant_ID`
   * **Attributes:** `Shop_Name`, `Contact_Name`, `Phone`, `Email` (Unique), [Status](file:///d:/DEPI-Round04/Graduation%20Project/models.py#26-36) (Enum: Pending, Approved), **`Address_ID` (FK)**.
4. **Zone** (Req 15, 16)
   * **PK:** `Zone_ID`
   * **Attributes:** `Zone_Name` (Unique), `GeoJSON_Boundary` (JSON), `Base_Delivery_Fee` (Decimal), `Active_Status` (Bool).

### (Warehouse & Inventory)

5. **Address** (Req 2.2, 4.1, 9.2)
   * **PK:** `Address_ID`
   * **Attributes:** `Street`, `District`, `City`, `Latitude` (Decimal), `Longitude` (Decimal), **`Zone_ID` (FK)**.
6. **Product** (Req 3.1, 3.2)
   * **PK:** `Product_ID`
   * **Attributes:** `Product_Name`, `Description`, `Price` (Decimal), `Stock_Quantity` (Int), **`Merchant_ID` (FK)**.
7. **Warehouse** (Req 6.1)
   * **PK:** `Warehouse_ID`
   * **Attributes:** `Warehouse_Name`, **`Address_ID` (FK)**.

### (Logistics & Execution)

8. **Shipment** (Req 4.1, 4.2)
   * **PK:** `Shipment_ID`
   * **Attributes:** [Status](file:///d:/DEPI-Round04/Graduation%20Project/models.py#26-36) (Enum: Pending, Assigned, InTransit, Delivered, Failed, Cancelled), `Creation_Date` (Timestamp), `Weight_KG` (Decimal), `COD_Amount` (Decimal), **`Merchant_ID` (FK)**, **`Destination_Address_ID` (FK)**, **`Warehouse_ID` (FK)**, **`Invoice_ID` (FK)**.
9. **Delivery_Attempt** (Req 5)
   * **PK:** `Attempt_ID`
   * **Attributes:** `Attempt_Number` (Sequence), [Status](file:///d:/DEPI-Round04/Graduation%20Project/models.py#26-36) (Enum: Success, Failed, Rescheduled), `OTP_Code` (String), `Photo_URL` (String), `Reason` (Text), `Timestamp`, **`Shipment_ID` (FK)**, **`Driver_ID` (FK)**.
10. **Driver** (Req 7.1)
    * **PK:** `Driver_ID`
    * **Attributes:** `Name`, `Phone` (Unique), `License_Number` (Unique), `License_Expiry`, `Current_Status` (Enum: Available, Offline, EnRoute), **`Zone_ID` (FK)**.
11. **Vehicle** (Req 8.1)
    * **PK:** `Vehicle_ID`
    * **Attributes:** `License_Plate` (Unique), `Vehicle_Model`, `Max_Capacity_KG` (Int), `Vehicle_Type` (Enum: Motorcycle, Car, Van).
12. **Route** (Req 9.1, 11)
    * **PK:** `Route_ID`
    * **Attributes:** `Route_Name`, [Status](file:///d:/DEPI-Round04/Graduation%20Project/models.py#26-36) (Enum: Planned, InProgress, Completed), **`Driver_ID` (FK)**, **`Vehicle_ID` (FK)**.
13. **Route_Stop** (Req 9.2)
    * **PK:** `Stop_ID`
    * **Attributes:** `Sequence_Order` (Int), **`Route_ID` (FK)**, **`Address_ID` (FK)**.

### (Financial & Feedback)

14. **Invoice** (Req 12.1)
    * **PK:** `Invoice_ID`
    * **Attributes:** `Total_Amount` (Decimal), `Payment_Status` (Enum: Paid, Unpaid), `Billing_Start`, `Billing_End`, **`Merchant_ID` (FK)**.
15. **Driver_Payment** (Req 13)
    * **PK:** `Payment_ID`
    * **Attributes:** `Total_Payout` (Decimal), `Distance_KM` (Decimal), `Completed_Deliveries_Count` (Int), **`Driver_ID` (FK)**, **`Route_ID` (FK)**.
16. **Feedback** (Req 14)
    * **PK:** `Feedback_ID`
    * **Attributes:** `Rating` (Int 1-5), `Comment` (Text), `Timestamp`, **`Shipment_ID` (FK)**.

### 🤖 AI Intelligence Layer (Proposed)

17. **Sentiment_Analysis**
    * **PK:** `Analysis_ID`
    * **Attributes:** `Sentiment_Score` (-1 to 1), `Priority` (Enum: Urgent, Normal), `Keywords`, **`Feedback_ID` (FK)**.
18. **Performance_Score**
    * **PK:** `Perf_ID`
    * **Attributes:** `Daily_Score` (Decimal), `Weighted_History`, `Tier` (Enum: Top, Good, Poor), **`Driver_ID` (FK)**.
19. **Demand_Forecast**
    * **PK:** `Forecast_ID`
    * **Attributes:** `Forecasted_Volume`, `Peak_Prediction`, `Forecast_Date`, **`Zone_ID` (FK)**.

---

## 2. Relationship Specification (Degrees, Cardinality, Participation)

| Relationship Matrix       | Entities Involved     | Degree | Cardinality Ratio | Participation          | Business Rule / Constraint                                                 |
| :------------------------ | :-------------------- | :----- | :---------------- | :--------------------- | :------------------------------------------------------------------------- |
| **Manage_Roles**    | Employee ↔ Role      | Binary | 1 : M             | Total (Role)           | One admin can manage many roles.                                           |
| **Supervisor**      | Employee ↔ Employee  | Unary  | 1 : M             | Partial                | Recursive: A manager supervises many employees.                            |
| **Shop_Catalog**    | Merchant ↔ Product   | Binary | 1 : M             | **Total (Both)** | No merchant without products (post-approval), no product without merchant. |
| **Zone_Coverage**   | Zone ↔ Address       | Binary | 1 : M             | Total (Address)        | Every address must be geofenced in a valid Zone.                           |
| **Origin_Point**    | Warehouse ↔ Shipment | Binary | 1 : M             | Total (Shipment)       | A shipment must originate from 1 warehouse.                                |
| **Batch_Billing**   | Invoice ↔ Shipment   | Binary | 1 : M             | Total (Shipment)       | An invoice groups many shipments; shipment must be invoiced.               |
| **Duty_Roster**     | Driver ↔ Route       | Binary | 1 : M             | Partial (Driver)       | A driver can handle many routes over time; Route needs 1 driver.           |
| **Vehicle_Pool**    | Vehicle ↔ Route      | Binary | 1 : M             | Total (Route)          | One vehicle per route; Vehicle used for many routes.                       |
| **Route_Stop_Flow** | Route ↔ Route_Stop   | Binary | 1 : M             | Total (Stop)           | A route consists of multiple ordered stops.                                |
| **POD_Evidence**    | Shipment ↔ Attempt   | Binary | 1 : M             | Total (Attempt)        | Shipment can have multiple fail/reschedule attempts.                       |
| **AI_Sentiment**    | Feedback ↔ AI_Sent   | Binary | 1 : 1             | Total (AI)             | Every feedback is analyzed by the AI engine.                               |
| **AI_Payout_Audit** | Driver_Pay ↔ Driver  | Binary | 1 : M             | Total (Pay)            | Driver payout record must be linked to 1 driver.                           |

---

## 3. Structural Constraints Summary

### Total Participation (MUST)

- **Shipment MUST** have a **Warehouse** and a **Destination Address**.
- **Product MUST** have a **Merchant**.
- **Address MUST** belong to a **Zone**.
- **Invoice MUST** belong to a **Merchant**.
- **Attempt MUST** belong to a **Shipment**.

### Partial Participation (MAY)

- **Employee MAY** not have a **Supervisor** (CEO/Top Admin).
- **Driver MAY** exist without an active **Vehicle** or **Route**.
- **Merchant MAY** temporarily have zero **Products** (if deleted/archived).
- **Shipment MAY** not yet be linked to an **Attempt** (if state is CREATED).
