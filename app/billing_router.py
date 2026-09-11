from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/billing", tags=["Billing & Subscriptions"])

# Pydantic Schemas
class InvoiceItem(BaseModel):
    id: str
    number: str
    date: str
    amount: float
    plan: str
    status: str
    method: str

class PaymentMethodItem(BaseModel):
    id: str
    type: str  # "bakong" | "card"
    name: str
    accountNumber: str
    isDefault: bool

class AddPaymentMethodRequest(BaseModel):
    type: str  # "bakong" | "card"
    accountName: str
    accountNumber: str
    expiry: Optional[str] = ""
    isDefault: Optional[bool] = False

class SubscriptionPlanItem(BaseModel):
    id: str
    name: str
    status: str
    priceUsd: float
    billingCycle: str
    nextRenewalDate: str
    autoRenew: bool
    perks: List[str]
    tenantTier: Optional[bool] = False

class PlanTierDetail(BaseModel):
    id: str
    name: str
    subtitle: str
    priceUsd: float
    isPopular: Optional[bool] = False
    isTenant: Optional[bool] = False
    badge: Optional[str] = None
    perks: List[str]
    limits: Dict[str, Any]

class QuotaMetric(BaseModel):
    id: str
    name: str
    used: float
    total: float
    unit: str
    pct: float
    color: str

class FeatureItem(BaseModel):
    id: str
    name: str
    description: str
    starter: str  # boolean or string value
    growth: str
    enterprise: str
    tenant: str

class FeatureCategory(BaseModel):
    category: str
    categoryKm: str
    items: List[FeatureItem]

class ChangePlanRequest(BaseModel):
    planId: str  # "tier-starter" | "tier-growth" | "tier-enterprise" | "tier-tenant"

class BillingOverview(BaseModel):
    subscription: SubscriptionPlanItem
    tiers: List[PlanTierDetail]
    featureCategories: List[FeatureCategory]
    quotas: List[QuotaMetric]
    paymentMethods: List[PaymentMethodItem]
    invoices: List[InvoiceItem]

# In-memory Store (Mock DB for Billing Microservice)
DB_SUBSCRIPTION = {
    "id": "tier-growth",
    "name": "Enterprise Growth Tier",
    "status": "active",
    "priceUsd": 49.0,
    "billingCycle": "monthly",
    "nextRenewalDate": "Oct 11, 2026",
    "autoRenew": True,
    "tenantTier": False,
    "perks": [
        "កាតាឡុកមុខម្ហូបគ្មានដែនកំណត់ (Unlimited Menu Items)",
        "តុឌីជីថល KHQR រហូតដល់ 100 តុ (100 Active QR Tables)",
        "បុគ្គលិកគិតលុយ និងមេចុងភៅ 15 នាក់ (15 Staff Accounts)",
        "របាយការណ៍វិភាគលក់ស៊ីជម្រៅ (Advanced Analytics)",
        "សេវាបម្រើអតិថិជន 24/7 អាទិភាពខ្ពស់ (Priority Support)",
        "Cloudinary CDN រូបភាពល្បឿនលឿន (High-Speed CDN)",
    ],
}

TIERS: Dict[str, Dict[str, Any]] = {
    "tier-starter": {
        "id": "tier-starter",
        "name": "Starter Lite",
        "subtitle": "សម្រាប់តូបអាហារ ហាងកាហ្វេតូច ឬ Food Truck",
        "priceUsd": 19.0,
        "isPopular": False,
        "isTenant": False,
        "badge": "STARTER",
        "limits": {
            "menuItems": 50,
            "tables": 15,
            "staff": 3,
            "branches": 1,
            "storageGB": 2,
        },
        "perks": [
            "កាតាឡុកមុខម្ហូប 50 មុខ (Up to 50 Menu Items)",
            "តុឌីជីថល 15 តុ ជាមួយ Bakong KHQR",
            "គណនីបុគ្គលិក 3 នាក់",
            "របាយការណ៍លក់មូលដ្ឋាន (Basic Daily Reports)",
            "ទំហំផ្ទុករូបភាព Cloudinary 2 GB",
        ],
    },
    "tier-growth": {
        "id": "tier-growth",
        "name": "Enterprise Growth",
        "subtitle": "សម្រាប់ហាងកាហ្វេ ភោជនីយដ្ឋាន និងប៊ីស្ត្រូមមាញឹក",
        "priceUsd": 49.0,
        "isPopular": True,
        "isTenant": False,
        "badge": "POPULAR",
        "limits": {
            "menuItems": -1,  # Unlimited
            "tables": 100,
            "staff": 15,
            "branches": 2,
            "storageGB": 10,
        },
        "perks": [
            "កាតាឡុកមុខម្ហូបគ្មានដែនកំណត់ (Unlimited Menu Items)",
            "តុឌីជីថល KHQR រហូតដល់ 100 តុ (100 Active QR Tables)",
            "បុគ្គលិកគិតលុយ និងមេចុងភៅ 15 នាក់ (15 Staff Accounts)",
            "ផ្ទះបាយឆ្លាតវៃ KDS និងសំឡេងប្រកាសកុម្ម៉ង់ផ្ទាល់",
            "របាយការណ៍វិភាគលក់ស៊ីជម្រៅ (Advanced Analytics)",
            "សេវាបម្រើអតិថិជន 24/7 អាទិភាពខ្ពស់",
            "Cloudinary CDN រូបភាពល្បឿនលឿន 10 GB",
        ],
    },
    "tier-enterprise": {
        "id": "tier-enterprise",
        "name": "Corporate Chain",
        "subtitle": "សម្រាប់ហាងដែលមានច្រើនសាខា និងម៉ាកយីហោល្បីៗ",
        "priceUsd": 99.0,
        "isPopular": False,
        "isTenant": False,
        "badge": "MULTI-STORE",
        "limits": {
            "menuItems": -1,
            "tables": -1,
            "staff": 50,
            "branches": 10,
            "storageGB": 30,
        },
        "perks": [
            "គ្រប់មុខងារ Growth Tier ទាំងអស់ (All Growth Features)",
            "គ្រប់គ្រងរហូតដល់ 10 សាខា (Centralized Multi-Store)",
            "តុឌីជីថល KHQR គ្មានដែនកំណត់ (Unlimited Tables)",
            "គណនីបុគ្គលិក 50 នាក់ និងសិទ្ធិ Role-based RBAC",
            "API Integration ផ្ទាល់ជាមួយប្រព័ន្ធ POS/ERP ក្នុងស្រុក",
            "អ្នកគ្រប់គ្រងគណនីផ្ទាល់ខ្លួន (Dedicated Account Manager)",
            "Cloudinary CDN រូបភាព 30 GB",
        ],
    },
    "tier-tenant": {
        "id": "tier-tenant",
        "name": "Dedicated Tenant Cloud (Tenant Plan)",
        "subtitle": "សម្រាប់ Franchise ធំៗ សម្ព័ន្ធក្រុមហ៊ុន និង SaaS White-label Tenant",
        "priceUsd": 199.0,
        "isPopular": False,
        "isTenant": True,
        "badge": "DEDICATED TENANT",
        "limits": {
            "menuItems": -1,
            "tables": -1,
            "staff": -1,
            "branches": -1,
            "storageGB": 100,
        },
        "perks": [
            "ស្ថាបត្យកម្មទិន្នន័យដាច់ដោយឡែក (Isolated Tenant DB Schema / VPC)",
            "Domain និង Branding ផ្ទាល់ខ្លួន White-Label (menu.brand.com)",
            "បង្កើត Sub-Tenants និងសាខាគ្មានដែនកំណត់ (Unlimited Tenants)",
            "Bakong KHQR Acquirer Merchant API និង Split Payment ស្វ័យប្រវត្តិ",
            "Full Open API Gateway, Webhooks Event Streaming គ្មានកំណត់",
            "កិច្ចសន្យាធានាស្ថិរភាព 99.99% Enterprise SLA",
            "ទំហំផ្ទុក Cloud Media 100 GB + Dedicated CDN Route",
            "វិស្វករប្រព័ន្ធប្រចាំការ 24/7 Dedicated Cloud Architect",
        ],
    },
}

DB_FEATURE_CATEGORIES = [
    {
        "category": "Tenant & Multi-Branch Architecture",
        "categoryKm": "ស្ថាបត្យកម្ម Tenant & ការគ្រប់គ្រងសាខា",
        "items": [
            {
                "id": "tenant-isolation",
                "name": "Multi-Tenant Data Isolation (VPC/Schema)",
                "description": "ទិន្នន័យត្រូវបានរក្សាទុកដោយឡែក ធានាសុវត្ថិភាពខ្ពស់កម្រិតសហគ្រាស",
                "starter": "false",
                "growth": "false",
                "enterprise": "false",
                "tenant": "true",
            },
            {
                "id": "custom-domain",
                "name": "Custom Domain & White-Label (menu.yourbrand.com)",
                "description": "ប្រើប្រាស់ Brand Name និង Domain ផ្ទាល់ខ្លួនទាំងស្រុង",
                "starter": "false",
                "growth": "false",
                "enterprise": "false",
                "tenant": "true",
            },
            {
                "id": "branches-count",
                "name": "ចំនួនសាខាដែលអនុញ្ញាត (Allowed Branches)",
                "description": "ចំនួនសាខាហាងដែលអាចដំណើរការក្នុងប្រព័ន្ធរួមមួយ",
                "starter": "1 សាខា",
                "growth": "2 សាខា",
                "enterprise": "10 សាខា",
                "tenant": "គ្មានដែនកំណត់ (Unlimited)",
            },
            {
                "id": "sub-tenants",
                "name": "ការបង្កើត Sub-Tenant Hub សម្រាប់ Franchise",
                "description": "គ្រប់គ្រងម្ចាស់ Franchise នីមួយៗជា Tenant ដោយឡែក",
                "starter": "false",
                "growth": "false",
                "enterprise": "false",
                "tenant": "true",
            },
            {
                "id": "rbac-permissions",
                "name": "Role-Based Access Control (RBAC) កម្រិតខ្ពស់",
                "description": "បែងចែកសិទ្ធិបុគ្គលិកតាមតួនាទី និងសាខានីមួយៗយ៉ាងម៉ត់ចត់",
                "starter": "កម្រិតមូលដ្ឋាន",
                "growth": "កម្រិតស្តង់ដារ",
                "enterprise": "កម្រិតពេញលេញ",
                "tenant": "កម្រិតសហគ្រាស (Custom Roles)",
            },
        ],
    },
    {
        "category": "Menu, Table QR & Ordering Engines",
        "categoryKm": "មុខងារម៉ឺនុយ កាតាឡុកតុ QR & ការកុម្ម៉ង់",
        "items": [
            {
                "id": "menu-catalog-limit",
                "name": "ចំនួនមុខម្ហូប និងភេសជ្ជៈ (Menu Catalog Items)",
                "description": "សមត្ថភាពបន្ថែមមុខម្ហូប និងរូបភាពក្នុងកាតាឡុក",
                "starter": "50 មុខ",
                "growth": "គ្មានដែនកំណត់",
                "enterprise": "គ្មានដែនកំណត់",
                "tenant": "គ្មានដែនកំណត់",
            },
            {
                "id": "active-tables-qr",
                "name": "តុឌីជីថល Dynamic Bakong QR",
                "description": "កូដ QR ឆ្លាតវៃសម្រាប់កុម្ម៉ង់ផ្ទាល់នៅតុជាមួយ Bakong KHQR",
                "starter": "15 តុ",
                "growth": "100 តុ",
                "enterprise": "គ្មានដែនកំណត់",
                "tenant": "គ្មានដែនកំណត់",
            },
            {
                "id": "kds-kitchen",
                "name": "Kitchen Display System (KDS) & Audio Broadcast",
                "description": "ផ្ទាំងបង្ហាញការកុម្ម៉ង់សម្រាប់ចុងភៅ និងសំឡេងប្រកាស",
                "starter": "false",
                "growth": "true",
                "enterprise": "true",
                "tenant": "true",
            },
            {
                "id": "inventory-low-stock",
                "name": "តាមដានស្តុក និងការជូនដំណឹងទំនិញជិតអស់",
                "description": "គ្រប់គ្រងស្តុកគ្រឿងផ្សំ និងសម្ភារៈក្នុងហាង",
                "starter": "false",
                "growth": "true",
                "enterprise": "true",
                "tenant": "true",
            },
            {
                "id": "reorder-drag-drop",
                "name": "តម្រៀបលំដាប់មុខម្ហូប (Drag & Drop Reordering)",
                "description": "ងាយស្រួលរៀបចំលំដាប់មុខម្ហូបបង្ហាញលើអេក្រង់អតិថិជន",
                "starter": "true",
                "growth": "true",
                "enterprise": "true",
                "tenant": "true",
            },
        ],
    },
    {
        "category": "Finances, Bakong KHQR & Settlement",
        "categoryKm": "ហិរញ្ញវត្ថុ ការទូទាត់ Bakong KHQR & របាយការណ៍",
        "items": [
            {
                "id": "platform-commission",
                "name": "កម្រៃជើងសារវេទិកា (Platform Commission)",
                "description": "ការកាត់កម្រៃលើរាល់ការកុម្ម៉ង់តាមរយៈប្រព័ន្ធ",
                "starter": "0% ឥតគិតថ្លៃ",
                "growth": "0% ឥតគិតថ្លៃ",
                "enterprise": "0% ឥតគិតថ្លៃ",
                "tenant": "0% ឥតគិតថ្លៃ",
            },
            {
                "id": "bakong-auto-debit",
                "name": "Bakong KHQR Auto-Debit & Settlement ផ្ទាល់",
                "description": "ផ្ទេរប្រាក់ចំណូលផ្ទាល់ចូលគណនីធនាគារក្នុងស្រុក (ABA, ACLEDA...)",
                "starter": "true",
                "growth": "true",
                "enterprise": "true",
                "tenant": "true",
            },
            {
                "id": "split-settlement",
                "name": "ការទូទាត់បែងចែកប្រាក់ចំណូលស្វ័យប្រវត្តិ (Split Payment)",
                "description": "បែងចែកប្រាក់ចំណូលរវាង Franchise Headquarter និងសាខា",
                "starter": "false",
                "growth": "false",
                "enterprise": "true",
                "tenant": "true",
            },
            {
                "id": "multi-currency",
                "name": "គណនា និងបង្ហាញរូបិយប័ណ្ណទ្វេ (USD & KHR)",
                "description": "គាំទ្រអត្រាប្តូរប្រាក់ជាក់ស្តែង និងការបង់ជាប្រាក់រៀល",
                "starter": "true",
                "growth": "true",
                "enterprise": "true",
                "tenant": "true",
            },
            {
                "id": "export-formats",
                "name": "ទាញយករបាយការណ៍ជា Excel, Word និង PDF",
                "description": "ឯកសាររបាយការណ៍គណនេយ្យពេញលេញ",
                "starter": "Excel, PDF",
                "growth": "Excel, Word, PDF",
                "enterprise": "Excel, Word, PDF",
                "tenant": "Excel, Word, PDF, JSON API",
            },
        ],
    },
    {
        "category": "Cloud Infrastructure, Storage & SLA",
        "categoryKm": "ហេដ្ឋារចនាសម្ព័ន្ធ Cloud ទំហំផ្ទុក & សេវាធានា SLA",
        "items": [
            {
                "id": "uptime-sla",
                "name": "កិច្ចសន្យាធានាស្ថិរភាពប្រព័ន្ធ (Uptime SLA)",
                "description": "ការធានាភាពមិនរអាក់រអួលនៃប្រព័ន្ធបម្រើអតិថិជន",
                "starter": "99.0%",
                "growth": "99.5%",
                "enterprise": "99.9%",
                "tenant": "99.99% Enterprise SLA",
            },
            {
                "id": "storage-cdn",
                "name": "ទំហំផ្ទុករូបភាព Cloudinary CDN ល្បឿនលឿន",
                "description": "សម្រាប់ផ្ទុករូបភាពមុខម្ហូបគុណភាពខ្ពស់ និងលឿនរហ័ស",
                "starter": "2 GB",
                "growth": "10 GB",
                "enterprise": "30 GB",
                "tenant": "100 GB Dedicated",
            },
            {
                "id": "support-level",
                "name": "កម្រិតសេវាបម្រើអតិថិជន (Customer Support)",
                "description": "ការជួយដោះស្រាយបញ្ហាបច្ចេកទេស និងប្រតិបត្តិការ",
                "starter": "អ៊ីមែលធម្មតា (48h)",
                "growth": "ជំនួយអាទិភាព (24h)",
                "enterprise": "Support 24/7 & Telegram",
                "tenant": "Dedicated Cloud Architect (15m SLA)",
            },
        ],
    },
    {
        "category": "Developer API, Webhooks & POS Integrations",
        "categoryKm": "Developer API, Webhooks & ការភ្ជាប់ជាមួយ POS",
        "items": [
            {
                "id": "rest-api-access",
                "name": "សិទ្ធិចូលប្រើប្រាស់ Full REST API Gateway",
                "description": "អាចតភ្ជាប់កម្មវិធីខាងក្រៅជាមួយប្រព័ន្ធកាតាឡុក និងការកុម្ម៉ង់",
                "starter": "false",
                "growth": "false",
                "enterprise": "true",
                "tenant": "true (Unlimited RPS)",
            },
            {
                "id": "webhooks-events",
                "name": "Webhooks Event Streaming (Real-time Order Events)",
                "description": "ផ្ញើដំណឹង Order Event ទៅកាន់ Server របស់អតិថិជនភ្លាមៗ",
                "starter": "false",
                "growth": "false",
                "enterprise": "true",
                "tenant": "true",
            },
            {
                "id": "pos-hardware-connect",
                "name": "ការភ្ជាប់ផ្ទាល់ជាមួយម៉ាស៊ីន POS & ម៉ាស៊ីនព្រីន Thermal",
                "description": "ព្រីនប័ណ្ណកុម្ម៉ង់ផ្ទាល់ពីបណ្តាញ Local Network",
                "starter": "false",
                "growth": "true",
                "enterprise": "true",
                "tenant": "true",
            },
        ],
    },
]

DB_QUOTAS = [
    {
        "id": "q-orders",
        "name": "ការកម្ម៉ង់ប្រចាំខែ (Monthly Orders)",
        "used": 4850,
        "total": 10000,
        "unit": "orders",
        "pct": 48.5,
        "color": "from-blue-500 to-indigo-600",
    },
    {
        "id": "q-tables",
        "name": "តុឌីជីថលសកម្ម (Active QR Tables)",
        "used": 34,
        "total": 100,
        "unit": "tables",
        "pct": 34.0,
        "color": "from-emerald-500 to-teal-600",
    },
    {
        "id": "q-staff",
        "name": "គណនីបុគ្គលិក (Staff Accounts)",
        "used": 9,
        "total": 15,
        "unit": "members",
        "pct": 60.0,
        "color": "from-amber-500 to-orange-600",
    },
    {
        "id": "q-storage",
        "name": "ផ្ទុកទិន្នន័យរូបភាព (Cloudinary Storage)",
        "used": 4.2,
        "total": 10.0,
        "unit": "GB",
        "pct": 42.0,
        "color": "from-purple-500 to-pink-600",
    },
    {
        "id": "q-tenants",
        "name": "សាខា / Sub-Tenants សកម្ម",
        "used": 2,
        "total": 5,
        "unit": "branches",
        "pct": 40.0,
        "color": "from-cyan-500 to-blue-600",
    },
]

DB_PAYMENT_METHODS = [
    {
        "id": "pm-1",
        "type": "bakong",
        "name": "Bakong KHQR Auto-Debit (ABA Bank)",
        "accountNumber": "000 889 012 (USD)",
        "isDefault": True,
    },
    {
        "id": "pm-2",
        "type": "card",
        "name": "Corporate Visa Debit Card",
        "accountNumber": "**** **** **** 4242",
        "isDefault": False,
    },
]

DB_INVOICES = [
    {
        "id": "inv-009",
        "number": "INV-2026-009",
        "date": "Sep 11, 2026",
        "amount": 49.0,
        "plan": "Enterprise Growth Tier - Monthly",
        "status": "paid",
        "method": "Bakong KHQR Auto-Debit (ABA *8890)",
    },
    {
        "id": "inv-008",
        "number": "INV-2026-008",
        "date": "Aug 11, 2026",
        "amount": 49.0,
        "plan": "Enterprise Growth Tier - Monthly",
        "status": "paid",
        "method": "Bakong KHQR Auto-Debit (ABA *8890)",
    },
    {
        "id": "inv-007",
        "number": "INV-2026-007",
        "date": "Jul 11, 2026",
        "amount": 49.0,
        "plan": "Enterprise Growth Tier - Monthly",
        "status": "paid",
        "method": "Corporate Visa (*4242)",
    },
    {
        "id": "inv-006",
        "number": "INV-2026-006",
        "date": "Jun 11, 2026",
        "amount": 49.0,
        "plan": "Enterprise Growth Tier - Monthly",
        "status": "paid",
        "method": "Corporate Visa (*4242)",
    },
    {
        "id": "inv-005",
        "number": "INV-2026-005",
        "date": "May 11, 2026",
        "amount": 19.0,
        "plan": "Starter Tier - Monthly",
        "status": "paid",
        "method": "Bakong KHQR Auto-Debit (ABA *8890)",
    },
]


@router.get("/overview", response_model=BillingOverview)
async def get_billing_overview():
    tier_list = [PlanTierDetail(**t) for t in TIERS.values()]
    feature_cats = [FeatureCategory(**fc) for fc in DB_FEATURE_CATEGORIES]
    return {
        "subscription": DB_SUBSCRIPTION,
        "tiers": tier_list,
        "featureCategories": feature_cats,
        "quotas": DB_QUOTAS,
        "paymentMethods": DB_PAYMENT_METHODS,
        "invoices": DB_INVOICES,
    }


@router.get("/plans", response_model=List[PlanTierDetail])
async def get_plans():
    return [PlanTierDetail(**t) for t in TIERS.values()]


@router.get("/features", response_model=List[FeatureCategory])
async def get_feature_matrix():
    return [FeatureCategory(**fc) for fc in DB_FEATURE_CATEGORIES]


@router.get("/subscription", response_model=SubscriptionPlanItem)
async def get_subscription():
    return DB_SUBSCRIPTION


@router.get("/quotas", response_model=List[QuotaMetric])
async def get_quotas():
    return DB_QUOTAS


@router.get("/payment-methods", response_model=List[PaymentMethodItem])
async def get_payment_methods():
    return DB_PAYMENT_METHODS


@router.post("/payment-methods", response_model=PaymentMethodItem, status_code=status.HTTP_201_CREATED)
async def add_payment_method(req: AddPaymentMethodRequest):
    new_id = f"pm-{len(DB_PAYMENT_METHODS) + 1}"
    is_default = bool(req.isDefault) or len(DB_PAYMENT_METHODS) == 0

    if is_default:
        for pm in DB_PAYMENT_METHODS:
            pm["isDefault"] = False

    masked_num = req.accountNumber
    if req.type == "card" and len(req.accountNumber.replace(" ", "")) >= 4:
        clean = req.accountNumber.replace(" ", "")
        masked_num = f"**** **** **** {clean[-4:]}"

    new_pm = {
        "id": new_id,
        "type": req.type,
        "name": req.accountName,
        "accountNumber": masked_num,
        "isDefault": is_default,
    }
    DB_PAYMENT_METHODS.append(new_pm)
    return new_pm


@router.delete("/payment-methods/{pm_id}", status_code=status.HTTP_200_OK)
async def delete_payment_method(pm_id: str):
    global DB_PAYMENT_METHODS
    found = False
    for pm in DB_PAYMENT_METHODS:
        if pm["id"] == pm_id:
            found = True
            break
    if not found:
        raise HTTPException(status_code=404, detail="Payment method not found")

    DB_PAYMENT_METHODS = [pm for pm in DB_PAYMENT_METHODS if pm["id"] != pm_id]
    if DB_PAYMENT_METHODS and not any(pm["isDefault"] for pm in DB_PAYMENT_METHODS):
        DB_PAYMENT_METHODS[0]["isDefault"] = True

    return {"message": "Payment method deleted successfully", "id": pm_id}


@router.patch("/payment-methods/{pm_id}/default", status_code=status.HTTP_200_OK)
async def set_default_payment_method(pm_id: str):
    target = None
    for pm in DB_PAYMENT_METHODS:
        if pm["id"] == pm_id:
            target = pm
            pm["isDefault"] = True
        else:
            pm["isDefault"] = False

    if not target:
        raise HTTPException(status_code=404, detail="Payment method not found")

    return target


@router.get("/invoices", response_model=List[InvoiceItem])
async def get_invoices():
    return DB_INVOICES


@router.post("/change-plan", response_model=SubscriptionPlanItem)
async def change_plan(req: ChangePlanRequest):
    global DB_SUBSCRIPTION
    if req.planId not in TIERS:
        raise HTTPException(status_code=400, detail="Invalid plan tier ID")

    tier_info = TIERS[req.planId]
    DB_SUBSCRIPTION["id"] = tier_info["id"]
    DB_SUBSCRIPTION["name"] = tier_info["name"]
    DB_SUBSCRIPTION["priceUsd"] = tier_info["priceUsd"]
    DB_SUBSCRIPTION["perks"] = tier_info["perks"]
    DB_SUBSCRIPTION["tenantTier"] = tier_info.get("isTenant", False)

    # Generate a new invoice for the plan change
    inv_num = f"INV-2026-{len(DB_INVOICES) + 1:03d}"
    now_str = datetime.now().strftime("%b %d, %Y")
    new_inv = {
        "id": f"inv-{len(DB_INVOICES) + 1:03d}",
        "number": inv_num,
        "date": now_str,
        "amount": tier_info["priceUsd"],
        "plan": f"{tier_info['name']} - Monthly",
        "status": "paid",
        "method": DB_PAYMENT_METHODS[0]["name"] if DB_PAYMENT_METHODS else "Bakong KHQR",
    }
    DB_INVOICES.insert(0, new_inv)

    return DB_SUBSCRIPTION
