export const metadata = { title: "Smart Document Intake" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body
        style={{
          fontFamily: "system-ui, -apple-system, sans-serif",
          margin: 0,
          padding: 24,
          maxWidth: 760,
          lineHeight: 1.5,
        }}
      >
        {children}
      </body>
    </html>
  );
}
