SELECT month, contact, COUNT(*) AS records, SUM(subscribed) AS subscriptions,
       AVG(subscribed) AS subscription_rate, SUM(campaign) AS reported_contacts
FROM observations
GROUP BY month, contact;
