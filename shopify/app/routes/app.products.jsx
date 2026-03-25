import { json } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { Page, Card, IndexTable, Badge, Text } from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import { authenticate } from "../shopify.server";

export const loader = async ({ request }) => {
  const { admin } = await authenticate.admin(request);

  const response = await admin.graphql(`
    query {
      products(first: 50) {
        edges {
          node {
            id
            title
            status
            totalInventory
            priceRangeV2 {
              minVariantPrice { amount currencyCode }
              maxVariantPrice { amount currencyCode }
            }
            vendor
            productType
          }
        }
      }
    }
  `);

  const data = await response.json();
  return json({ products: data.data.products.edges });
};

function statusTone(status) {
  switch (status) {
    case "ACTIVE": return "success";
    case "DRAFT": return "attention";
    case "ARCHIVED": return "critical";
    default: return "new";
  }
}

function stockTone(inventory) {
  if (inventory === null || inventory === undefined) return "new";
  if (inventory > 10) return "success";
  if (inventory > 0) return "warning";
  return "critical";
}

function stockLabel(inventory) {
  if (inventory === null || inventory === undefined) return "Unknown";
  if (inventory > 10) return "In Stock";
  if (inventory > 0) return `Low Stock (${inventory})`;
  return "Out of Stock";
}

const resourceName = { singular: "product", plural: "products" };

const headings = [
  { title: "Product" },
  { title: "Vendor" },
  { title: "Type" },
  { title: "Price" },
  { title: "Status" },
  { title: "Stock" },
];

export default function ProductsPage() {
  const { products } = useLoaderData();

  return (
    <Page title="Products">
      <TitleBar title="Products" />
      <Card padding="0">
        <IndexTable
          resourceName={resourceName}
          itemCount={products.length}
          headings={headings}
          selectable={false}
          emptyState={<Text tone="subdued" as="p">No products found.</Text>}
        >
          {products.map(({ node }, index) => {
            const shortId = node.id.split("/").pop();
            const { minVariantPrice, maxVariantPrice } = node.priceRangeV2;
            const currency = minVariantPrice.currencyCode;
            const minPrice = parseFloat(minVariantPrice.amount).toFixed(2);
            const maxPrice = parseFloat(maxVariantPrice.amount).toFixed(2);
            const price =
              minPrice === maxPrice
                ? `${currency} ${minPrice}`
                : `${currency} ${minPrice}–${maxPrice}`;

            return (
              <IndexTable.Row id={shortId} key={node.id} position={index}>
                <IndexTable.Cell>
                  <Text variant="bodyMd" fontWeight="bold" as="span">{node.title}</Text>
                </IndexTable.Cell>
                <IndexTable.Cell>{node.vendor || "—"}</IndexTable.Cell>
                <IndexTable.Cell>{node.productType || "—"}</IndexTable.Cell>
                <IndexTable.Cell>{price}</IndexTable.Cell>
                <IndexTable.Cell>
                  <Badge tone={statusTone(node.status)}>
                    {node.status.charAt(0) + node.status.slice(1).toLowerCase()}
                  </Badge>
                </IndexTable.Cell>
                <IndexTable.Cell>
                  <Badge tone={stockTone(node.totalInventory)}>
                    {stockLabel(node.totalInventory)}
                  </Badge>
                </IndexTable.Cell>
              </IndexTable.Row>
            );
          })}
        </IndexTable>
      </Card>
    </Page>
  );
}
