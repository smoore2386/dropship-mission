import { json } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { Page, Card, IndexTable, Badge, Text } from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import { authenticate } from "../shopify.server";

export const loader = async ({ request }) => {
  const { admin } = await authenticate.admin(request);

  const response = await admin.graphql(`
    query {
      orders(first: 50, sortKey: CREATED_AT, reverse: true) {
        edges {
          node {
            id
            name
            displayFulfillmentStatus
            displayFinancialStatus
            createdAt
            customer { firstName lastName email }
            totalPriceSet { shopMoney { amount currencyCode } }
            lineItems(first: 5) {
              edges { node { title quantity } }
            }
            fulfillments(first: 1) {
              trackingInfo { number url }
              status
            }
          }
        }
      }
    }
  `);

  const data = await response.json();
  return json({ orders: data.data.orders.edges });
};

function fulfillmentTone(status) {
  switch (status) {
    case "FULFILLED": return "success";
    case "UNFULFILLED": return "warning";
    case "IN_PROGRESS": return "info";
    case "PARTIALLY_FULFILLED": return "warning";
    case "PENDING_FULFILLMENT": return "attention";
    case "ON_HOLD": return "attention";
    case "RESTOCKED": return "info";
    default: return "new";
  }
}

function fulfillmentLabel(status) {
  return status
    ? status.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
    : "Unknown";
}

const resourceName = { singular: "order", plural: "orders" };

const headings = [
  { title: "Order ID" },
  { title: "Customer" },
  { title: "Product" },
  { title: "Total" },
  { title: "Status" },
  { title: "Date" },
];

export default function OrdersPage() {
  const { orders } = useLoaderData();

  return (
    <Page title="Orders">
      <TitleBar title="Orders" />
      <Card padding="0">
        <IndexTable
          resourceName={resourceName}
          itemCount={orders.length}
          headings={headings}
          selectable={false}
          emptyState={<Text tone="subdued" as="p">No orders found.</Text>}
        >
          {orders.map(({ node }, index) => {
            const shortId = node.id.split("/").pop();
            const customer = node.customer
              ? `${node.customer.firstName} ${node.customer.lastName}`.trim()
              : "Guest";
            const firstItem = node.lineItems.edges[0]?.node;
            const product = firstItem
              ? `${firstItem.title}${node.lineItems.edges.length > 1 ? ` +${node.lineItems.edges.length - 1} more` : ""}`
              : "—";
            const { amount, currencyCode } = node.totalPriceSet.shopMoney;
            const total = `${currencyCode} ${parseFloat(amount).toFixed(2)}`;
            const status = node.displayFulfillmentStatus;
            const date = new Date(node.createdAt).toLocaleDateString();

            return (
              <IndexTable.Row id={shortId} key={node.id} position={index}>
                <IndexTable.Cell>
                  <Text variant="bodyMd" fontWeight="bold" as="span">{node.name}</Text>
                </IndexTable.Cell>
                <IndexTable.Cell>{customer}</IndexTable.Cell>
                <IndexTable.Cell>{product}</IndexTable.Cell>
                <IndexTable.Cell>{total}</IndexTable.Cell>
                <IndexTable.Cell>
                  <Badge tone={fulfillmentTone(status)}>{fulfillmentLabel(status)}</Badge>
                </IndexTable.Cell>
                <IndexTable.Cell>{date}</IndexTable.Cell>
              </IndexTable.Row>
            );
          })}
        </IndexTable>
      </Card>
    </Page>
  );
}
