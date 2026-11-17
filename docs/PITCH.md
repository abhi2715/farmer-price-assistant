# AgriRoute: one-page pitch

**Sell smarter. Earn more.** AgriRoute tells every small farmer what to sell, where, when and to whom for the best net profit. It then connects them directly to buyers.

### Problem
- India has ~86% small and marginal farmers. Most sell at the **nearest mandi, on harvest day**, with no view of prices at other mandis or next week.
- For perishables, farmers typically get **about a third of the consumer rupee** (RBI working paper, 2024, tomato/onion/potato). The rest goes to intermediaries, waste and timing.
- Price swings are violent (tomato prices can move 2–5× within weeks). Spoilage, transport and mandi fees eat what's left, and none of it is visible at the moment of decision.
- Existing price apps show **yesterday's price**. They don't show the **decision**: net of costs, risk and perishability.

### Solution
- **3 taps (or one sentence of voice)** in Kannada, Hindi or English. Crop → quantity → best (mandi, day), showing the rupees you take home, a worst case, and *why*.
- **Forecasts** for each crop × mandi up to 30 days, backtested. Three model families compete and the best one serves.
- **Optimizer** that nets out transport, fees, spoilage (temperature-aware) and holding cost, and splits big lots across markets.
- **Direct marketplace**: lots matched to traders, processors, retailers and exporters by crop, grade, quantity, distance and price. The surplus is split fairly, and pickup routes are optimised.
- **Alerts** by SMS/WhatsApp when a price is about to move. An **offline-first PWA** for low-end Android on 2G.

### Market
- India produces **~350 Mt of fruit and vegetables** and **~330 Mt of food grains** a year, traded through ~7,000 regulated mandis. Agricultural output is worth more than **₹40 lakh crore**.
- **Beachhead:** Karnataka horticulture belts (Kolar, Chikkaballapur, Hubballi, Mysuru) and their tomato, onion, chilli and banana farmers, plus buyers in Bengaluru (FPOs, processors, modern retail, exporters).
- **Expansion:** pulses and cotton in North Karnataka, then Maharashtra, Andhra Pradesh and Telangana with the same crops and languages, then pan-India via FPO partnerships.

### Revenue model
1. **Marketplace commission:** 0.5% from the farmer (below the 3–6% mandi commission they pay today) + 1.5% from the buyer, who saves on sourcing and quality risk. *Example: a ₹39,100 tomato deal earns ₹782.*
2. **Buyer SaaS:** demand planning, supply forecasts and pickup routing for processors and retailers (₹5–25k/month).
3. **Data & risk:** anonymised price and arrival intelligence for lenders, insurers and agri-input companies; credit scoring from transaction history.
4. **Logistics take-rate:** pooled transport for matched lots (later).

### Why now / why us
Agmarknet and Open-Meteo data are open; UPI, ONDC and WhatsApp reach rural India; and cheap Android phones are everywhere. The hard part is turning data into one trustworthy, explainable **decision** in the farmer's language. AgriRoute does that end to end, and every match makes the marketplace and the models better.

**Ask:** pilot with 3 FPOs (≈2,000 farmers) and 10 Bengaluru buyers for one season. Target metric: **net ₹ per quintal vs. nearest-mandi-today baseline**.
