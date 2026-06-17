export const metadata = { title: "Smart Document Intake" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body
        style={{
          fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
          margin: 0,
          lineHeight: 1.5,
        }}
      >
        {children}
      </body>
    </html>
  );
}
