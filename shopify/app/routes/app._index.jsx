import { json } from "@remix-run/node";
import { useLoaderData, useNavigate } from "@remix-run/react";
import {
  Page,
  Layout,
  Card,
  DataTable,
  Badge,
  Button,
  Text,
  BlockStack,
  InlineStack,
  InlineGrid,
} from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import { authenticate } from "../shopify.server";

export const loader = async ({ request }) => {
  const { admin } = await authenticate.admin(request);

  const ordersResponse = await admin.graphql(`
    query {
      orders(first: 5, sortKey: CREATED_AT, reverse: true) {
        edges {
          node {
            id
            name
            displayFulfillmentStatus
            displayFinancialStatus
            createdAt
            totalPriceSet { shopMoney { amount currencyCode } }
            customer { firstName lastName }
            lineItems(first: 3) {
              edges { node { title quantity } }
            }
          }
        }
      }
      ordersCount: ordersCount { count }
    }
  `);

  const ordersData = await ordersResponse.json();
  return json({
    orders: ordersData.data.orders.edges,
    ordersCount: ordersData.data.ordersCount.count,
  });
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

export default function Dashboard() {
  const { orders, ordersCount } = useLoaderData();
  const navigate = useNavigate();

  const rows = orders.map(({ node }) => {
    const orderId = node.name;
    const firstItem = node.lineItems.edges[0]?.node;
    const product = firstItem ? firstItem.title : "—";
    const customer = node.customer
      ? `${node.customer.firstName} ${node.customer.lastName}`.trim()
      : "Guest";
    const status = node.displayFulfillmentStatus;
    const date = new Date(node.createdAt).toLocaleDateString();

    return [
      orderId,
      product,
      customer,
      <Badge tone={fulfillmentTone(status)} key={node.id}>
        {fulfillmentLabel(status)}
      </Badge>,
      date,
    ];
  });

  return (
    <Page>
      <TitleBar title="Dropship Mission" />
      <BlockStack gap="500">
        <InlineGrid columns={4} gap="400">
          <Card>
            <BlockStack gap="100">
              <Text variant="headingSm" as="h3" tone="subdued">Total Orders</Text>
              <Text variant="heading2xl" as="p">{ordersCount ?? "—"}</Text>
            </BlockStack>
          </Card>
          <Card>
            <BlockStack gap="100">
              <Text variant="headingSm" as="h3" tone="subdued">Pending Fulfillment</Text>
              <Text variant="heading2xl" as="p">—</Text>
            </BlockStack>
          </Card>
          <Card>
            <BlockStack gap="100">
              <Text variant="headingSm" as="h3" tone="subdued">Revenue Today</Text>
              <Text variant="heading2xl" as="p">—</Text>
            </BlockStack>
          </Card>
          <Card>
            <BlockStack gap="100">
              <Text variant="headingSm" as="h3" tone="subdued">Active Products</Text>
              <Text variant="heading2xl" as="p">—</Text>
            </BlockStack>
          </Card>
        </InlineGrid>

        <Card>
          <BlockStack gap="400">
            <Text variant="headingMd" as="h2">Recent Orders</Text>
            {rows.length === 0 ? (
              <Text tone="subdued">No orders found.</Text>
            ) : (
              <DataTable
                columnContentTypes={["text", "text", "text", "text", "text"]}
                headings={["Order", "Product", "Customer", "Status", "Date"]}
                rows={rows}
              />
            )}
          </BlockStack>
        </Card>

        <Card>
          <BlockStack gap="300">
            <Text variant="headingMd" as="h2">Quick Actions</Text>
            <InlineStack gap="300">
              <Button onClick={() => navigate("/app/orders")}>View Orders</Button>
              <Button onClick={() => navigate("/app/suppliers")}>Manage Suppliers</Button>
              <Button onClick={() => navigate("/app/products")}>Sync Products</Button>
            </InlineStack>
          </BlockStack>
        </Card>
      </BlockStack>
    </Page>
  );
}
